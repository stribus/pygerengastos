from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from importlib import import_module
from typing import Any, Callable, Iterable, Sequence, cast
import concurrent.futures
import json
import os
import textwrap
import threading
import tomllib

from litellm import completion

from src.database import ItemParaClassificacao
from src.logger import setup_logging
from src.medidas import extrair_tamanho

logger = setup_logging(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "modelos_llm.toml"
DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
DEFAULT_MAX_TOKENS = 8000
MAX_ITENS_POR_CHAMADA = 50
BACKGROUND_LOAD_TIMEOUT = 5.0  # Timeout em segundos para aguardar carregamento em background
_ENV_LOADED = False

# Cache thread-safe para modelos carregados
_modelos_cache: list[ModeloConfig] | None = None
_modelos_cache_lock = threading.Lock()
_carregamento_em_andamento: concurrent.futures.Future[list[ModeloConfig]] | None = None
_carregamento_lock = threading.Lock()


@dataclass(frozen=True)
class ModeloConfig:
	nome: str
	api_key_env: str
	max_tokens: int
	max_itens: int
	timeout: float
	nome_amigavel: str | None = None
	extra_body: dict[str, Any] | None = None


def _obter_modelos_fallback() -> list[ModeloConfig]:
	"""
	Retorna configuração mínima hardcoded para Gemini quando TOML falha.
	
	Este fallback garante que o sistema nunca fique em estado degradado silencioso.
	"""
	logger.warning("Usando configuração fallback hardcoded para Gemini")
	return [
		ModeloConfig(
			nome=DEFAULT_MODEL,
			api_key_env="GEMINI_API_KEY",
			max_tokens=DEFAULT_MAX_TOKENS,
			max_itens=MAX_ITENS_POR_CHAMADA,
			timeout=30.0,
			nome_amigavel="Gemini 2.5 Flash Lite (Fallback)",
			extra_body=None
		)
	]


def _carregar_modelos_toml() -> list[ModeloConfig]:
	"""Carrega configurações de modelos do arquivo TOML."""
	if not CONFIG_FILE.exists():
		logger.error(f"Arquivo de configuração não encontrado: {CONFIG_FILE}")
		return _obter_modelos_fallback()

	try:
		with open(CONFIG_FILE, "rb") as f:
			data = tomllib.load(f)

		modelos: list[ModeloConfig] = []
		for idx, m in enumerate(data.get("modelos", [])):
			# Validação explícita de campos obrigatórios para evitar KeyError silencioso
			campos_obrigatorios = ("nome", "api_key_env")
			campos_ausentes = [campo for campo in campos_obrigatorios if campo not in m]
			if campos_ausentes:
				logger.error(
					f"Modelo na posição {idx} em {CONFIG_FILE} está malformado: "
					f"campos obrigatórios ausentes: {', '.join(campos_ausentes)}. "
					f"Entrada: {m!r}"
				)
				continue

			try:
				modelos.append(ModeloConfig(
					nome=m["nome"],
					api_key_env=m["api_key_env"],
					max_tokens=m.get("max_tokens", DEFAULT_MAX_TOKENS),
					max_itens=m.get("max_itens", MAX_ITENS_POR_CHAMADA),
					timeout=float(m.get("timeout", 30.0)),
					nome_amigavel=m.get("nome_amigavel"),
					extra_body=m.get("extra_body")
				))
			except Exception as e_modelo:
				logger.error(
					f"Erro ao processar modelo na posição {idx} "
					f"({m.get('nome', '<sem nome>')}): {e_modelo}"
				)
		
		if not modelos:
			logger.error(f"Nenhum modelo válido encontrado em {CONFIG_FILE}, usando fallback")
			return _obter_modelos_fallback()
		
		logger.info(f"Carregados {len(modelos)} modelos de LLM de {CONFIG_FILE}")
		return modelos
	except FileNotFoundError:
		# Arquivo pode ter sido removido entre o exists() e o open()
		logger.error(f"Arquivo de configuração não encontrado durante a leitura: {CONFIG_FILE}")
		return _obter_modelos_fallback()
	except tomllib.TOMLDecodeError as e:
		logger.error(f"Erro de sintaxe TOML em {CONFIG_FILE}: {e}")
		return _obter_modelos_fallback()
	except (OSError, IOError) as e:
		logger.error(f"Erro de E/S ao ler arquivo de configuração {CONFIG_FILE}: {e}")
		return _obter_modelos_fallback()
	except Exception as e:
		# Qualquer outro erro inesperado
		logger.exception(f"Erro inesperado ao carregar {CONFIG_FILE}: {e}")
		return _obter_modelos_fallback()


def iniciar_carregamento_background() -> concurrent.futures.Future[list[ModeloConfig]]:
	"""
	Inicia carregamento de modelos em background thread.
	
	Retorna:
		Future que será resolvido quando os modelos forem carregados.
	"""
	global _carregamento_em_andamento
	
	with _carregamento_lock:
		if _carregamento_em_andamento is not None:
			logger.debug("Carregamento em andamento já existe, reutilizando")
			return _carregamento_em_andamento
		
		logger.info("Iniciando carregamento de modelos LLM em background")
		executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-loader")
		_carregamento_em_andamento = executor.submit(_carregar_modelos_toml)
		
		# Cleanup do executor após conclusão
		def _cleanup(_future: concurrent.futures.Future) -> None:
			executor.shutdown(wait=False)
		
		_carregamento_em_andamento.add_done_callback(_cleanup)
		return _carregamento_em_andamento


def obter_modelos_carregados(aguardar: bool = True) -> list[ModeloConfig]:
	"""
	Retorna modelos carregados, usando cache se disponível.
	
	Args:
		aguardar: Se True, aguarda carregamento em background se ainda não concluído.
		         Se False, retorna fallback se cache vazio e carregamento pendente.
	
	Retorna:
		Lista de ModeloConfig carregados do TOML ou fallback.
	"""
	global _modelos_cache, _carregamento_em_andamento
	
	# Fast path: cache já populado (sem lock para performance)
	if _modelos_cache is not None:
		return _modelos_cache
	
	# Slow path: precisa carregar ou aguardar carregamento
	# Usa lock do cache para evitar race conditions
	with _modelos_cache_lock:
		# Double-check: outro thread pode ter populado cache enquanto esperávamos lock
		if _modelos_cache is not None:
			return _modelos_cache
		
		# Se há carregamento em andamento
		with _carregamento_lock:
			future = _carregamento_em_andamento
		
		if future is not None:
			if aguardar:
				logger.debug("Aguardando conclusão do carregamento em background")
				try:
					modelos = future.result(timeout=BACKGROUND_LOAD_TIMEOUT)
				except concurrent.futures.TimeoutError:
					logger.warning("Timeout aguardando carregamento, usando fallback")
					modelos = _obter_modelos_fallback()
				except Exception as e:
					logger.exception(f"Erro no carregamento em background: {e}")
					modelos = _obter_modelos_fallback()
			else:
				# Não aguardar, usar fallback
				if future.done():
					try:
						modelos = future.result()
					except Exception as e:
						logger.exception(f"Erro ao obter resultado do future: {e}")
						modelos = _obter_modelos_fallback()
				else:
					logger.debug("Carregamento em andamento, retornando fallback sem aguardar")
					modelos = _obter_modelos_fallback()
		else:
			# Sem carregamento em andamento, carregar agora de forma síncrona
			# Já estamos dentro do lock, então apenas um thread faz isso
			logger.debug("Sem carregamento em andamento, carregando de forma síncrona")
			modelos = _carregar_modelos_toml()
		
		# Atualizar cache (já dentro do lock)
		_modelos_cache = modelos
		return modelos


def recarregar_modelos() -> list[ModeloConfig]:
	"""
	Recarrega configurações de modelos do TOML, invalidando cache.
	
	Útil para atualizar configurações sem reiniciar a aplicação.
	
	Retorna:
		Lista de modelos recarregados.
	"""
	global _modelos_cache, _carregamento_em_andamento
	
	logger.info("Recarregando configurações de modelos LLM")
	
	# Invalidar cache
	with _modelos_cache_lock:
		_modelos_cache = None
	
	# Cancelar carregamento em andamento se existir
	with _carregamento_lock:
		if _carregamento_em_andamento is not None:
			_carregamento_em_andamento.cancel()
			_carregamento_em_andamento = None
	
	# Carregar de forma síncrona
	modelos = _carregar_modelos_toml()
	
	# Atualizar cache
	with _modelos_cache_lock:
		_modelos_cache = modelos
	
	logger.info(f"Modelos recarregados: {len(modelos)} disponíveis")
	return modelos


def obter_modelos_disponiveis() -> list[str]:
	"""Retorna a lista de IDs de modelos disponíveis."""
	return [modelo.nome for modelo in obter_modelos_carregados()]


def obter_modelos_com_nomes_amigaveis() -> dict[str, str]:
	"""
	Retorna um dicionário mapeando nomes amigáveis para IDs de modelos.

	Retorno:
		Dict com estrutura {nome_amigavel: model_id}

	Exemplo:
		{
			"Gemini 2.5 Flash Lite (Padrão)": "gemini/gemini-2.5-flash-lite",
			"LLaMA 3 70B (NVIDIA)": "nvidia_nim/meta/llama3-70b-instruct",
			...
		}

	Nota: Se um modelo não tiver nome amigável definido no TOML,
	      o ID do modelo será usado como chave (fallback).
	"""
	return {
		(modelo.nome_amigavel or modelo.nome): modelo.nome
		for modelo in obter_modelos_carregados()
	}


@dataclass
class FalhaModelo:
	modelo: str
	motivo: str


class RespostaLLMInvalidaError(ValueError):
	"""Erro ao interpretar JSON retornado pelo LLM."""


class FalhaModeloError(RuntimeError):
	"""Erro ao classificar com um modelo específico."""

	def __init__(
		self,
		*,
		modelo: str,
		motivo: str,
		itens_restantes: list[ItemParaClassificacao],
		causa: Exception | None = None,
		resultados_parciais: list[ClassificacaoResultado] | None = None,
	):
		super().__init__(motivo)
		self.modelo = modelo
		self.motivo = motivo
		self.itens_restantes = itens_restantes
		self.causa = causa
		self.resultados_parciais = resultados_parciais or []


@dataclass(frozen=True)
class _RespostaLLM:
	categoria: str
	confianca: float | None = None
	justificativa: str | None = None
	produto_nome: str | None = None
	produto_marca: str | None = None
	tamanho: str | None = None


LoadDotenvCallable = Callable[..., bool]
_LOAD_DOTENV_FUNC: LoadDotenvCallable | None = None


def _get_load_dotenv() -> LoadDotenvCallable:
	global _LOAD_DOTENV_FUNC
	if _LOAD_DOTENV_FUNC is not None:
		return _LOAD_DOTENV_FUNC
	try:
		module = import_module("dotenv")
	except ModuleNotFoundError as exc:
		raise RuntimeError(
			"A biblioteca python-dotenv não está instalada. Execute 'pip install python-dotenv'."
		) from exc
	load_func = getattr(module, "load_dotenv", None)
	if not callable(load_func):
		raise RuntimeError("A instalação python-dotenv não expôs a função load_dotenv().")
	load_callable = cast(LoadDotenvCallable, load_func)
	_LOAD_DOTENV_FUNC = load_callable
	return load_callable


@dataclass(slots=True)
class ClassificacaoResultado:
	chave_acesso: str
	sequencia: int
	categoria: str
	confianca: float | None = None
	origem: str = "gemini-litellm"
	modelo: str | None = None
	observacoes: str | None = None
	resposta_json: str | None = None
	produto_nome: str | None = None
	produto_marca: str | None = None
	produto_id: int | None = None
	tamanho: str | None = None


class LLMClassifier:
	"""Cliente LiteLLM para classificar itens via modelos Gemini."""

	def __init__(
		self,
		*,
		api_key: str | None = None,
		model: str = DEFAULT_MODEL,
		temperature: float = 0.1,
		max_tokens: int = DEFAULT_MAX_TOKENS,
		timeout: float = 30.0,
		categorias: Sequence[str] | None = None,
		model_priority: Sequence[str] | None = None,
	):
		self._ensure_env()
		self.model = model or DEFAULT_MODEL
		self.temperature = temperature
		self.max_tokens = max_tokens
		self._timeout = timeout
		self.categorias_disponiveis = [cat for cat in (categorias or []) if cat]
		self._model_priority = list(model_priority) if model_priority else [self.model]
		self._api_key_override: dict[str, str] = {}
		# Itens que nenhum modelo classificou na última chamada de classificar_itens
		self.itens_nao_classificados: list[ItemParaClassificacao] = []
		if api_key:
			self._api_key_override[self.model] = api_key

		# Configuração global de retry via env var
		try:
			self._num_retries = int(os.getenv("LLM_NUM_RETRIES", "2"))
		except ValueError:
			self._num_retries = 2

	def classificar_itens(
		self,
		itens: Sequence[ItemParaClassificacao],
		*,
		model_priority: Sequence[str] | None = None,
		progress_callback: Callable[[str], None] | None = None,
	) -> list[ClassificacaoResultado]:
		self.itens_nao_classificados = []
		if not itens:
			return []

		resultados: list[ClassificacaoResultado] = []
		itens_pendentes = list(itens)
		falhas: list[FalhaModelo] = []
		limite_anterior: int | None = None
		ultima_causa: Exception | None = None

		ordem_modelos = self._resolver_model_priority(model_priority)
		if not ordem_modelos:
			raise RuntimeError("Nenhum modelo configurado para classificação.")

		for modelo in ordem_modelos:
			config = self._obter_config_modelo(modelo)
			api_key = self._obter_api_key(config)
			if not api_key:
				motivo = "api_key_ausente"
				logger.warning("Modelo %s ignorado: %s", modelo, motivo)
				falhas.append(FalhaModelo(modelo=modelo, motivo=motivo))
				self._emitir_progresso(progress_callback, f"Modelo {modelo} ignorado: API key não configurada.")
				continue

			limite_em_uso = config.max_itens
			if limite_anterior is not None:
				limite_em_uso = min(limite_anterior, config.max_itens)
				if config.max_itens < limite_anterior:
					self._emitir_progresso(
						progress_callback,
						f"Modelo {modelo} usa lotes menores (até {config.max_itens} itens). Reagrupando...",
					)

			self._emitir_progresso(progress_callback, f"Tentando modelo {modelo}...")
			self.model = config.nome
			self.max_tokens = config.max_tokens
			self._timeout = config.timeout

			try:
				resultados_modelo, itens_pendentes = self._classificar_com_modelo(
					itens_pendentes,
					config=config,
					api_key=api_key,
					max_itens=limite_em_uso,
				)
			except FalhaModeloError as exc:
				falhas.append(FalhaModelo(modelo=exc.modelo, motivo=exc.motivo))
				logger.warning(
					"Falha ao classificar com %s: %s",
					exc.modelo,
					exc.motivo,
					exc_info=True,
				)
				self._emitir_progresso(
					progress_callback,
					f"Falha com {exc.modelo}: {exc.motivo}. Tentando próximo modelo...",
				)
				resultados.extend(exc.resultados_parciais)
				itens_pendentes = exc.itens_restantes
				limite_anterior = limite_em_uso
				ultima_causa = exc.causa
				continue

			resultados.extend(resultados_modelo)
			limite_anterior = limite_em_uso
			if not itens_pendentes:
				return resultados

			# Resposta válida, mas incompleta: os itens omitidos vão para o próximo modelo
			falhas.append(FalhaModelo(modelo=modelo, motivo=f"{len(itens_pendentes)} item(ns) sem resposta"))
			logger.warning("Modelo %s não classificou %s item(ns)", modelo, len(itens_pendentes))
			self._emitir_progresso(
				progress_callback,
				f"{modelo} não classificou {len(itens_pendentes)} item(ns). Tentando próximo modelo...",
			)

		if itens_pendentes:
			resumo = "; ".join(f"{falha.modelo}={falha.motivo}" for falha in falhas)
			if not resumo:
				resumo = "nenhuma tentativa executada"
			if not resultados:
				if ultima_causa is not None:
					raise ultima_causa
				raise RuntimeError(
					f"Falha ao classificar itens após tentar todos os modelos. {resumo}"
				)
			# Salva o que foi classificado e deixa os demais pendentes para revisão
			logger.warning(
				"%s item(ns) ficaram sem classificação após tentar todos os modelos. %s",
				len(itens_pendentes),
				resumo,
			)
			self.itens_nao_classificados = itens_pendentes

		return resultados

	def _resolver_model_priority(self, model_priority: Sequence[str] | None) -> list[str]:
		if model_priority is not None:
			return [modelo for modelo in model_priority if modelo]
		if self._model_priority:
			return list(self._model_priority)
		return [self.model]

	def _obter_config_modelo(self, modelo: str) -> ModeloConfig:
		"""Obtém configuração do modelo do TOML ou retorna config padrão."""
		for config in obter_modelos_carregados():
			if config.nome == modelo:
				return config

		# Fallback para modelos não configurados no TOML
		return ModeloConfig(
			nome=modelo,
			api_key_env="GEMINI_API_KEY",
			max_tokens=self.max_tokens,
			max_itens=MAX_ITENS_POR_CHAMADA,
			timeout=self._timeout,
		)

	def _obter_api_key(self, config: ModeloConfig) -> str | None:
		if config.nome in self._api_key_override:
			return self._api_key_override[config.nome]
		return os.getenv(config.api_key_env)

	def _emitir_progresso(self, callback: Callable[[str], None] | None, mensagem: str) -> None:
		if callback:
			callback(mensagem)

	def _classificar_com_modelo(
		self,
		itens: Sequence[ItemParaClassificacao],
		*,
		config: ModeloConfig,
		api_key: str,
		max_itens: int,
	) -> tuple[list[ClassificacaoResultado], list[ItemParaClassificacao]]:
		lista_itens = list(itens)
		if not lista_itens:
			return [], []

		resultados: list[ClassificacaoResultado] = []
		nao_classificados: list[ItemParaClassificacao] = []
		blocos = list(_dividir_em_blocos(lista_itens, max_itens))
		for indice_bloco, bloco in enumerate(blocos):
			try:
				payload = self._montar_payload(bloco)
				conteudo, resposta_raw = self._executar_chamada(payload, config=config, api_key=api_key)
				mapeamento = self._interpretar_resposta(conteudo)
			except Exception as exc:
				restantes = nao_classificados + [item for b in blocos[indice_bloco:] for item in b]
				motivo = _resumir_erro(exc)
				raise FalhaModeloError(
					modelo=config.nome,
					motivo=motivo,
					itens_restantes=restantes,
					causa=exc,
					resultados_parciais=resultados,
				) from exc

			resposta_json = json.dumps(
				{"chunk": indice_bloco + 1, "payload": payload, "resposta": resposta_raw},
				ensure_ascii=False,
			)

			# Item sem resposta ou com categoria inválida (inclusive bloco inteiro com
			# mapeamento vazio) volta como pendente para o próximo modelo
			for item in bloco:
				resposta = mapeamento.get(item.sequencia)
				categoria = _normalizar_categoria(resposta.categoria) if resposta else None
				if not categoria:
					nao_classificados.append(item)
					continue
				resultados.append(
					ClassificacaoResultado(
						chave_acesso=item.chave_acesso,
						sequencia=item.sequencia,
						categoria=categoria,
						confianca=resposta.confianca,
						origem=_definir_origem_modelo(self.model),
						modelo=self.model,
						observacoes=resposta.justificativa,
						resposta_json=resposta_json,
						produto_nome=resposta.produto_nome,
						produto_marca=resposta.produto_marca,
						tamanho=resposta.tamanho,
					)
				)

		return resultados, nao_classificados

	def sugerir_tamanhos(
		self,
		itens: Sequence[ItemParaClassificacao],
		*,
		model_priority: Sequence[str] | None = None,
	) -> dict[tuple[str, int], str]:
		"""Pede à IA só o tamanho da embalagem dos itens; retorna {(chave, sequência): "473ML"}.

		Usado para itens que não passam pela classificação do LLM (cache
		semântico) ou já classificados. Os itens são numerados pela posição no
		lote, então notas diferentes podem ir juntas. Item sem resposta segura
		fica de fora; lote com erro vai para o próximo modelo. O tamanho é
		opcional: sem nenhum modelo disponível, retorna vazio.
		"""
		tamanhos: dict[tuple[str, int], str] = {}
		pendentes = list(itens)
		for modelo in self._resolver_model_priority(model_priority):
			if not pendentes:
				break
			try:
				config = self._obter_config_modelo(modelo)
				api_key = self._obter_api_key(config)
			except Exception as exc:  # noqa: BLE001 - o tamanho nunca bloqueia a classificação
				logger.warning("Modelo %s indisponível para tamanhos: %s", modelo, _resumir_erro(exc))
				continue
			if not api_key:
				continue
			com_erro: list[ItemParaClassificacao] = []
			for inicio in range(0, len(pendentes), config.max_itens):
				lote = pendentes[inicio : inicio + config.max_itens]
				try:
					conteudo, _ = self._executar_chamada(
						self._montar_payload_tamanhos(lote, config.nome), config=config, api_key=api_key
					)
					respostas = _interpretar_tamanhos(conteudo)
				except Exception as exc:  # noqa: BLE001 - o tamanho nunca bloqueia a classificação
					logger.warning("Falha ao pedir tamanhos a %s: %s", modelo, _resumir_erro(exc))
					com_erro.extend(lote)
					continue
				for indice, item in enumerate(lote, start=1):
					if respostas.get(indice):
						tamanhos[(item.chave_acesso, item.sequencia)] = respostas[indice]
			pendentes = com_erro
		if pendentes:
			logger.warning("%s item(ns) ficaram sem resposta de tamanho da IA.", len(pendentes))
		return tamanhos

	def _montar_payload_tamanhos(self, itens: Sequence[ItemParaClassificacao], modelo: str) -> dict[str, Any]:
		linhas = "\n".join(f"- #{indice} — {item.descricao}" for indice, item in enumerate(itens, start=1))
		# A lista entra depois do dedent: linhas inseridas sem recuo o anulariam
		prompt = textwrap.dedent(
			"""
				Informe o peso ou volume da embalagem de cada produto de supermercado abaixo
				(ex.: "473ml", "1kg", "350g", "2l"). As descrições vêm de notas fiscais e
				podem estar abreviadas ou cortadas.

				Só responda o tamanho se tiver segurança (ex.: produto com embalagem única
				conhecida). Se não souber, use null. Não chute.

				FORMATO DE RESPOSTA (apenas JSON):
				{"itens": [{"indice": 1, "tamanho": "473ml"}, {"indice": 2, "tamanho": null}]}

				ITENS:
			"""
		) + linhas
		return {
			"model": modelo,
			"temperature": self.temperature,
			"max_tokens": self.max_tokens,
			"messages": [
				{"role": "system", "content": "Você responde apenas com JSON válido."},
				{"role": "user", "content": prompt.strip()},
			],
		}

	def _executar_chamada(
		self,
		payload: dict[str, Any],
		*,
		config: ModeloConfig,
		api_key: str,
	) -> tuple[str, dict[str, Any]]:
		logger.debug("Enviando payload para LiteLLM (%s): %s", config.nome, json.dumps(payload, ensure_ascii=False))
		# Remove 'model' do payload para evitar duplicação com model=config.nome explícito
		payload_limpo = {k: v for k, v in payload.items() if k != "model"}

		# Injeta parâmetros extras se configurado para o modelo
		if config.extra_body:
			payload_limpo["extra_body"] = config.extra_body

		try:
			response_obj = completion(
				model=config.nome,
				api_key=api_key,
				request_timeout=config.timeout,
				num_retries=self._num_retries,
				**cast(dict[str, Any], payload_limpo),
			)
		except Exception as exc:  # pragma: no cover - erro propagado para fluxo geral
			logger.exception("Erro ao chamar LiteLLM (%s): %s", config.nome, exc)
			raise
		json_data = _normalizar_resposta(response_obj)
		logger.debug("Resposta do LiteLLM (%s): %s", config.nome, json.dumps(json_data, ensure_ascii=False))
		conteudo = _extrair_conteudo(json_data)
		return conteudo, json_data

	def _montar_payload(self, itens: Sequence[ItemParaClassificacao]) -> dict[str, Any]:
		contexto_estabelecimento = itens[0].emitente_nome or "Estabelecimento desconhecido"
		contexto_data = itens[0].emissao_iso or "Data não informada"
		linhas: list[str] = []
		for item in itens:
			#valor = _formatar_decimal(item.valor_total)
			quantidade = _formatar_decimal(item.quantidade)
			unidade = item.unidade or ""
			linhas.append(
				f"#{item.sequencia} — {item.descricao} | quantidade: {quantidade} {unidade} "
			)
		linhas_formatadas = "\n".join(f"- {linha}" for linha in linhas)
		categorias_texto = ""
		if self.categorias_disponiveis:
			categorias_unicas = ", ".join(sorted(set(self.categorias_disponiveis)))
			categorias_texto = f"Categorias disponíveis: {categorias_unicas}.\n"

		prompt = textwrap.dedent(
			f"""
				Você classifica itens de notas fiscais em categorias de orçamento doméstico.
				Estabelecimento: {contexto_estabelecimento} | Data: {contexto_data}

				{categorias_texto}
				INSTRUÇÕES:
				1. Use as categorias disponíveis
				2. Extraia nome e marca base do produto quando possível
				3. Seja objetivo nas justificativas (máx 5 palavras)
				4. Responda APENAS com JSON válido
				5. "tamanho": peso ou volume da embalagem (ex.: "473ml", "1kg") de item
				   vendido por unidade, só se tiver segurança; senão null. Para item
				   vendido por KG ou L, use null (a quantidade já é a medida)

				FORMATO DE RESPOSTA:
				{{
					"itens": [
						{{"sequencia": 1, "categoria": "alimentacao", "confianca": 0.84, "produto": {{"nome_base": "Arroz tipo 1", "marca_base": "Tio João"}}, "tamanho": "5kg", "justificativa": "alimento básico"}}
					]
				}}

				ITENS PARA CLASSIFICAR:
				{linhas_formatadas}
			"""
		)

		return {
			"model": self.model,
			"temperature": self.temperature,
			"max_tokens": self.max_tokens,
			"messages": [
				{
					"role": "system",
					"content": "Você é um classificador de itens de notas fiscais. Responda apenas com JSON válido.",
				},
				{"role": "user", "content": prompt.strip()},
			],
		}

	def _interpretar_resposta(self, conteudo: str) -> dict[int, _RespostaLLM]:
		if not conteudo:
			return {}
		try:
			dados = json.loads(_extrair_json_text(conteudo))
		except json.JSONDecodeError as e:
			logger.error(
				"Resposta do LLM não pôde ser decodificada como JSON: \n %s \n\n erro: %s",
				conteudo,
				str(e),
			)
			raise RespostaLLMInvalidaError(str(e)) from e

		itens_dados: Iterable[dict[str, object]]
		if isinstance(dados, dict):
			itens_dados = dados.get("itens") or dados.get("items") or []
		elif isinstance(dados, list):
			itens_dados = dados
		else:
			return {}

		mapeamento: dict[int, _RespostaLLM] = {}
		for entrada in itens_dados:
			if not isinstance(entrada, dict):
				continue
			sequencia = entrada.get("sequencia") or entrada.get("item") or entrada.get("indice")
			categoria = entrada.get("categoria")
			if sequencia is None or categoria is None:
				continue
			sequencia_str = str(sequencia).strip()
			if not sequencia_str:
				continue
			try:
				sequencia_int = int(sequencia_str)
			except (TypeError, ValueError):
				continue
			produto_info = entrada.get("produto") or entrada.get("produto_padronizado")
			if isinstance(produto_info, dict):
				produto_nome = produto_info.get("nome_base") or produto_info.get("nome")
				produto_marca = produto_info.get("marca_base") or produto_info.get("marca")
				tamanho = entrada.get("tamanho") or produto_info.get("tamanho")
			else:
				produto_nome = entrada.get("produto_nome")
				produto_marca = entrada.get("produto_marca")
				tamanho = entrada.get("tamanho")

			mapeamento[sequencia_int] = _RespostaLLM(
				categoria=str(categoria),
				confianca=_normalizar_conf(entrada.get("confianca")),
				justificativa=cast(str | None, entrada.get("justificativa") or entrada.get("motivo")),
				produto_nome=cast(str | None, produto_nome),
				produto_marca=cast(str | None, produto_marca),
				tamanho=_tamanho_valido(tamanho),
			)
		return mapeamento

	@staticmethod
	def _ensure_env() -> None:
		global _ENV_LOADED
		if _ENV_LOADED:
			return
		load_dotenv_func = _get_load_dotenv()
		env_path = PROJECT_ROOT / ".env"
		if env_path.exists():
			load_dotenv_func(dotenv_path=str(env_path), override=False)
		else:
			load_dotenv_func(override=False)
		_ENV_LOADED = True


def _extrair_conteudo(resposta: dict[str, Any]) -> str:
	choices = resposta.get("choices")
	if not isinstance(choices, list) or not choices:
		return ""
	mensagem = choices[0]
	if isinstance(mensagem, dict):
		mensagem = mensagem.get("message")
	if isinstance(mensagem, dict):
		conteudo = mensagem.get("content")
		if isinstance(conteudo, str):
			return conteudo.strip()
	return ""


def _normalizar_resposta(resposta: object) -> dict[str, Any]:
	if isinstance(resposta, dict):
		return resposta
	if hasattr(resposta, "model_dump") and callable(getattr(resposta, "model_dump")):
		return cast(dict[str, Any], resposta.model_dump())  # type: ignore[no-any-return]
	if hasattr(resposta, "dict") and callable(getattr(resposta, "dict")):
		return cast(dict[str, Any], resposta.dict())  # type: ignore[no-any-return]
	if hasattr(resposta, "__dict__"):
		return cast(dict[str, Any], vars(resposta))
	raise TypeError("Resposta inesperada retornada pelo LiteLLM")


def _extrair_json_text(conteudo: str) -> str:
	inicio = conteudo.find("{")
	fim = conteudo.rfind("}")
	if inicio == -1 or fim == -1 or fim <= inicio:
		return conteudo
	return conteudo[inicio : fim + 1]


def _normalizar_categoria(valor: object | None) -> str | None:
	if valor is None:
		return None
	texto = str(valor).strip()
	return texto or None


def _tamanho_valido(valor: object | None) -> str | None:
	"""Tamanho respondido pela IA ("473ml" → "473ML"), ou None se não for peso/volume."""
	if not isinstance(valor, str):
		return None
	texto = " ".join(valor.upper().split())
	return texto if extrair_tamanho(texto) else None


def _interpretar_tamanhos(conteudo: str) -> dict[int, str]:
	"""Resposta de sugerir_tamanhos: {índice: tamanho válido}."""
	dados = json.loads(_extrair_json_text(conteudo)) if conteudo else {}
	itens_dados = dados.get("itens", []) if isinstance(dados, dict) else dados
	tamanhos: dict[int, str] = {}
	for entrada in itens_dados if isinstance(itens_dados, list) else []:
		if not isinstance(entrada, dict):
			continue
		tamanho = _tamanho_valido(entrada.get("tamanho"))
		try:
			indice = int(entrada.get("indice"))
		except (TypeError, ValueError):
			continue
		if tamanho:
			tamanhos[indice] = tamanho
	return tamanhos


def _normalizar_conf(valor: object | None) -> float | None:
	if valor is None:
		return None
	if isinstance(valor, (int, float)):
		return max(0.0, min(1.0, float(valor)))
	texto = str(valor).replace(",", ".")
	try:
		return max(0.0, min(1.0, float(texto)))
	except ValueError:
		return None


def _formatar_decimal(valor: Decimal | None) -> str:
	if valor is None:
		return "0.00"
	return f"{valor:.2f}"


def _resumir_erro(exc: Exception) -> str:
	mensagem = str(exc) or exc.__class__.__name__
	classe = exc.__class__.__name__
	texto = f"{classe}: {mensagem}" if mensagem else classe
	return texto[:300]


def _definir_origem_modelo(modelo: str) -> str:
	if modelo.startswith("gemini/"):
		return "gemini-litellm"
	if modelo.startswith("nvidia_nim/"):
		return "nvidia-nim"
	if modelo.startswith("openai/"):
		return "openai-litellm"
	return "litellm"


def _dividir_em_blocos(
	itens: Sequence[ItemParaClassificacao], tamanho_bloco: int
) -> Iterable[Sequence[ItemParaClassificacao]]:
	"""Divide os itens em blocos de até ``tamanho_bloco``, um conjunto por nota.

	A resposta do LLM é mapeada só pela sequência, que se repete entre notas;
	por isso um bloco nunca mistura itens de chaves de acesso diferentes.
	"""
	if tamanho_bloco <= 0:
		raise ValueError("tamanho_bloco precisa ser positivo")
	por_nota: dict[str, list[ItemParaClassificacao]] = {}
	for item in itens:
		por_nota.setdefault(item.chave_acesso, []).append(item)
	for itens_nota in por_nota.values():
		for inicio in range(0, len(itens_nota), tamanho_bloco):
			yield itens_nota[inicio : inicio + tamanho_bloco]
