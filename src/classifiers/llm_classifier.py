from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from importlib import import_module
from typing import Any, Callable, Iterable, Sequence, cast
import json
import os
import textwrap

from litellm import completion

from src.database import ItemParaClassificacao
from src.logger import setup_logging

logger = setup_logging(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
DEFAULT_MAX_TOKENS = 8000
MAX_ITENS_POR_CHAMADA = 50
_ENV_LOADED = False


@dataclass(frozen=True)
class ModeloConfig:
	nome: str
	api_key_env: str
	max_tokens: int
	max_itens: int
	timeout: float


DEFAULT_MODELOS = [
	ModeloConfig(
		nome="gemini/gemini-2.5-flash-lite",
		api_key_env="GEMINI_API_KEY",
		max_tokens=DEFAULT_MAX_TOKENS,
		max_itens=MAX_ITENS_POR_CHAMADA,
		timeout=30.0,
	),
	ModeloConfig(
		nome="nvidia_nim/meta/llama3-70b-instruct",
		api_key_env="NVIDIA_API_KEY",
		max_tokens=4096,
		max_itens=20,
		timeout=45.0,
	),
	ModeloConfig(
		nome="nvidia_nim/moonshotai/kimi-k2.5",
		api_key_env="NVIDIA_API_KEY",
		max_tokens=8192,
		max_itens=25,
		timeout=45.0,
	),
	ModeloConfig(
		nome="openai/gpt-4o",
		api_key_env="OPENAI_API_KEY",
		max_tokens=4096,
		max_itens=30,
		timeout=30.0,
	),
]


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
	):
		super().__init__(motivo)
		self.modelo = modelo
		self.motivo = motivo
		self.itens_restantes = itens_restantes
		self.causa = causa


@dataclass(frozen=True)
class _RespostaLLM:
	categoria: str
	confianca: float | None = None
	justificativa: str | None = None
	produto_nome: str | None = None
	produto_marca: str | None = None


LoadDotenvCallable = Callable[..., bool]
_LOAD_DOTENV_FUNC: LoadDotenvCallable | None = None


def _normalizar_chave_modelo_env(nome_modelo: str) -> str:
	texto = "".join((ch if ch.isalnum() else "_") for ch in nome_modelo)
	return texto.upper()


def _ler_int_env(nome: str, padrao: int) -> int:
	valor = os.getenv(nome)
	if not valor:
		return padrao
	try:
		return int(valor)
	except ValueError:
		return padrao


def _ler_float_env(nome: str, padrao: float) -> float:
	valor = os.getenv(nome)
	if not valor:
		return padrao
	try:
		return float(valor)
	except ValueError:
		return padrao


def _carregar_configs_modelo() -> dict[str, ModeloConfig]:
	configs: dict[str, ModeloConfig] = {}
	for modelo in DEFAULT_MODELOS:
		chave_env = _normalizar_chave_modelo_env(modelo.nome)
		api_key_env = os.getenv(f"LLM_MODEL_{chave_env}_API_KEY_ENV", modelo.api_key_env)
		max_tokens = _ler_int_env(f"LLM_MODEL_{chave_env}_MAX_TOKENS", modelo.max_tokens)
		max_itens = _ler_int_env(f"LLM_MODEL_{chave_env}_MAX_ITENS", modelo.max_itens)
		timeout = _ler_float_env(f"LLM_MODEL_{chave_env}_TIMEOUT", modelo.timeout)
		configs[modelo.nome] = ModeloConfig(
			nome=modelo.nome,
			api_key_env=api_key_env,
			max_tokens=max_tokens,
			max_itens=max_itens,
			timeout=timeout,
		)
	return configs


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
		self._model_configs = _carregar_configs_modelo()
		self._api_key_override: dict[str, str] = {}
		if api_key:
			self._api_key_override[self.model] = api_key
		self._num_retries = _ler_int_env("LLM_NUM_RETRIES", 2)

	def classificar_itens(
		self,
		itens: Sequence[ItemParaClassificacao],
		*,
		model_priority: Sequence[str] | None = None,
		progress_callback: Callable[[str], None] | None = None,
	) -> list[ClassificacaoResultado]:
		if not itens:
			return []

		resultados: list[ClassificacaoResultado] = []
		itens_pendentes = list(itens)
		falhas: list[FalhaModelo] = []
		limite_anterior: int | None = None

		ordem_modelos = self._resolver_model_priority(model_priority)
		if not ordem_modelos:
			raise RuntimeError("Nenhum modelo configurado para classificação.")

		for indice_modelo, modelo in enumerate(ordem_modelos):
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
				itens_pendentes = exc.itens_restantes
				limite_anterior = limite_em_uso
				if indice_modelo == len(ordem_modelos) - 1 and exc.causa is not None:
					raise exc.causa
				continue

			resultados.extend(resultados_modelo)
			limite_anterior = limite_em_uso
			if not itens_pendentes:
				return resultados

		if itens_pendentes:
			resumo = "; ".join(f"{falha.modelo}={falha.motivo}" for falha in falhas)
			if not resumo:
				resumo = "nenhuma tentativa executada"
			raise RuntimeError(
				f"Falha ao classificar itens após tentar todos os modelos. {resumo}"
			)

		return resultados

	def _resolver_model_priority(self, model_priority: Sequence[str] | None) -> list[str]:
		if model_priority is not None:
			return [modelo for modelo in model_priority if modelo]
		if self._model_priority:
			return list(self._model_priority)
		return [self.model]

	def _obter_config_modelo(self, modelo: str) -> ModeloConfig:
		config = self._model_configs.get(modelo)
		if config:
			return config
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
		for inicio in range(0, len(lista_itens), max_itens):
			bloco = lista_itens[inicio : inicio + max_itens]
			try:
				payload = self._montar_payload(bloco)
				conteudo, resposta_raw = self._executar_chamada(payload, config=config, api_key=api_key)
				mapeamento = self._interpretar_resposta(conteudo)
				if not mapeamento:
					continue
			except Exception as exc:  # pragma: no cover - comportamento coberto indiretamente
				restantes = lista_itens[inicio:]
				motivo = _resumir_erro(exc)
				raise FalhaModeloError(
					modelo=config.nome,
					motivo=motivo,
					itens_restantes=restantes,
					causa=exc,
				) from exc

			resposta_json = json.dumps(
				{"chunk": (inicio // max_itens) + 1, "payload": payload, "resposta": resposta_raw},
				ensure_ascii=False,
			)

			for item in bloco:
				resposta = mapeamento.get(item.sequencia)
				if resposta is None:
					continue
				categoria = _normalizar_categoria(resposta.categoria)
				if not categoria:
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
					)
				)

		return resultados, []

	def _executar_chamada(
		self,
		payload: dict[str, Any],
		*,
		config: ModeloConfig,
		api_key: str,
	) -> tuple[str, dict[str, Any]]:
		logger.debug("Enviando payload para LiteLLM (%s): %s", config.nome, json.dumps(payload, ensure_ascii=False))
		# Remove 'model' do payload para evitar duplicação com model=config.nome
		payload_sem_model = {k: v for k, v in payload.items() if k != "model"}
		try:
			response_obj = completion(
				model=config.nome,
				api_key=api_key,
				request_timeout=config.timeout,
				num_retries=self._num_retries,
				**cast(dict[str, Any], payload_sem_model),
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

				FORMATO DE RESPOSTA:
				{{
					"itens": [
						{{"sequencia": 1, "categoria": "alimentacao", "confianca": 0.84, "produto": {{"nome_base": "Arroz tipo 1", "marca_base": "Tio João"}}, "justificativa": "alimento básico"}}
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
			else:
				produto_nome = entrada.get("produto_nome")
				produto_marca = entrada.get("produto_marca")

			mapeamento[sequencia_int] = _RespostaLLM(
				categoria=str(categoria),
				confianca=_normalizar_conf(entrada.get("confianca")),
				justificativa=cast(str | None, entrada.get("justificativa") or entrada.get("motivo")),
				produto_nome=cast(str | None, produto_nome),
				produto_marca=cast(str | None, produto_marca),
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
	if tamanho_bloco <= 0:
		raise ValueError("tamanho_bloco precisa ser positivo")
	lista_itens = list(itens)
	for inicio in range(0, len(lista_itens), tamanho_bloco):
		yield lista_itens[inicio : inicio + tamanho_bloco]
