from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from importlib import import_module
from typing import Any, Callable, Iterable, Sequence, cast
import json
import logging
import os
import textwrap

from litellm import completion

from src.database import ItemParaClassificacao
from src.logger import setup_logging

logger = setup_logging(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
DEFAULT_MAX_TOKENS = 8000
_ENV_LOADED = False


@dataclass(frozen=True)
class _RespostaLLM:
	categoria: str
	confianca: float | None = None
	justificativa: str | None = None
	produto_nome: str | None = None
	produto_marca: str | None = None


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
	):
		self._ensure_env()
		self.api_key = api_key or os.getenv("GEMINI_API_KEY") 
		if not self.api_key:
			raise RuntimeError("Configure a variável GEMINI_API_KEY no ambiente ou arquivo .env")
		self.model = model or DEFAULT_MODEL
		self.temperature = temperature
		self.max_tokens = max_tokens
		self._timeout = timeout
		self.categorias_disponiveis = [cat for cat in (categorias or []) if cat]

	def classificar_itens(
		self, itens: Sequence[ItemParaClassificacao]
	) -> list[ClassificacaoResultado]:
		if not itens:
			return []

		payload = self._montar_payload(itens)
		conteudo, resposta_raw = self._executar_chamada(payload)
		mapeamento = self._interpretar_resposta(conteudo)
		if not mapeamento:
			return []

		resposta_json = json.dumps(
			{"payload": payload, "resposta": resposta_raw}, ensure_ascii=False
		)

		resultados: list[ClassificacaoResultado] = []
		for item in itens:
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
					modelo=self.model,
					observacoes=resposta.justificativa,
					resposta_json=resposta_json,
					produto_nome=resposta.produto_nome,
					produto_marca=resposta.produto_marca,
				)
			)
		return resultados

	def _executar_chamada(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
		logger.debug("Enviando payload para LiteLLM/Gemini: %s", json.dumps(payload, ensure_ascii=False))
		try:
			response_obj = completion(
				request_timeout=self._timeout,
				api_key=self.api_key,
				**cast(dict[str, Any], payload),
			)
		except Exception as exc:  # pragma: no cover - erro propagado para fluxo geral
			logger.exception("Erro ao chamar LiteLLM/Gemini: %s", exc)
			raise
		json_data = _normalizar_resposta(response_obj)
		logger.debug("Resposta do LiteLLM/Gemini: %s", json.dumps(json_data, ensure_ascii=False))
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
			logger.error("Resposta do LLM não pôde ser decodificada como JSON: \n %s \n\n erro: %s", conteudo, str(e))
			return {}

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
