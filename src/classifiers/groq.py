from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from importlib import import_module
from typing import Callable, Iterable, Sequence, cast
import json
import os
import textwrap

import httpx

from src.database import ItemParaClassificacao

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
_ENV_LOADED = False


@dataclass(frozen=True)
class _RespostaGroq:
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
	origem: str = "groq"
	modelo: str | None = None
	observacoes: str | None = None
	resposta_json: str | None = None
	produto_nome: str | None = None
	produto_marca: str | None = None


class GroqClassifier:
	"""Cliente simples para a API da Groq focado em classificação de itens."""

	def __init__(
		self,
		*,
		api_key: str | None = None,
		model: str = DEFAULT_MODEL,
		temperature: float = 0.1,
		max_tokens: int = 400,
		client: httpx.Client | None = None,
		timeout: float = 30.0,
		categorias: Sequence[str] | None = None,
	):
		self._ensure_env()
		self.api_key = api_key or os.getenv("GROQ_API_KEY")
		if not self.api_key:
			raise RuntimeError("Configure a variável GROQ_API_KEY no ambiente ou arquivo .env")
		self.model = model or DEFAULT_MODEL
		self.temperature = temperature
		self.max_tokens = max_tokens
		self._client = client
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
					origem="groq",
					modelo=self.model,
					observacoes=resposta.justificativa,
					resposta_json=resposta_json,
					produto_nome=resposta.produto_nome,
					produto_marca=resposta.produto_marca,
				)
			)
		return resultados

	def _executar_chamada(self, payload: dict[str, object]) -> tuple[str, dict[str, object]]:
		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}
		client = self._client or httpx.Client(timeout=self._timeout)
		close_client = self._client is None
		try:
			response = client.post(
				GROQ_CHAT_COMPLETIONS_URL, headers=headers, json=payload, timeout=self._timeout
			)
			response.raise_for_status()
			json_data: dict[str, object] = response.json()
			conteudo = _extrair_conteudo(json_data)
			return conteudo, json_data
		finally:
			if close_client:
				client.close()

	def _montar_payload(self, itens: Sequence[ItemParaClassificacao]) -> dict[str, object]:
		contexto_estabelecimento = itens[0].emitente_nome or "Estabelecimento desconhecido"
		contexto_data = itens[0].emissao_iso or "Data não informada"
		linhas: list[str] = []
		for item in itens:
			valor = _formatar_decimal(item.valor_total)
			quantidade = _formatar_decimal(item.quantidade)
			unidade = item.unidade or ""
			linhas.append(
				f"#{item.sequencia} — {item.descricao} | quantidade: {quantidade} {unidade} | valor total: R$ {valor}"
			)
		linhas_formatadas = "\n".join(f"- {linha}" for linha in linhas)
		categorias_texto = ""
		if self.categorias_disponiveis:
			categorias_unicas = ", ".join(sorted(set(self.categorias_disponiveis)))
			categorias_texto = f"Categorias esperadas: {categorias_unicas}.\n\n"

		prompt = textwrap.dedent(
			f"""
				Você é um especialista em finanças pessoais. Classifique cada item listado abaixo em
				categorias de orçamento como alimentação, limpeza, higiene, farmácia, petshop,
				serviços ou "outros". Observe o estabelecimento {contexto_estabelecimento}
				e a data {contexto_data}.

				{categorias_texto}
				Responda SOMENTE com JSON seguindo o formato:
				{{
					"itens": [
						{{
							"sequencia": 1,
							"categoria": "alimentacao",
							"confianca": 0.84,
							"produto": {{"nome_base": "Arroz branco 5kg", "marca_base": "Tio João"}},
							"justificativa": "explicação curta"
						}}
					]
				}}

				Inclua em cada item o objeto "produto" com o nome_base padronizado e, quando possível,
				uma marca_base. Use apenas palavras sem acentos para as categorias, seguindo os valores
				providenciados.

				Itens:
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
					"content": "Você classifica itens de notas fiscais em categorias de orçamento. Use apenas uma palavra para a categoria.",
				},
				{"role": "user", "content": prompt.strip()},
			],
		}

	def _interpretar_resposta(self, conteudo: str) -> dict[int, _RespostaGroq]:
		if not conteudo:
			return {}
		try:
			dados = json.loads(_extrair_json_text(conteudo))
		except json.JSONDecodeError:
			return {}

		itens_dados: Iterable[dict[str, object]]
		if isinstance(dados, dict):
			itens_dados = dados.get("itens") or dados.get("items") or []
		elif isinstance(dados, list):
			itens_dados = dados
		else:
			return {}

		mapeamento: dict[int, _RespostaGroq] = {}
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

			mapeamento[sequencia_int] = _RespostaGroq(
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


def _extrair_conteudo(resposta: dict[str, object]) -> str:
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
