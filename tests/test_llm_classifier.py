from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Sequence, cast
from unittest.mock import Mock, patch , MagicMock

import json
import os

import pytest
from litellm.exceptions import RateLimitError

from src.classifiers import ClassificacaoResultado, classificar_itens_pendentes
from src.classifiers.llm_classifier import LLMClassifier, MAX_ITENS_POR_CHAMADA, ModeloConfig
from src.database import ItemParaClassificacao, salvar_nota
from src.scrapers import receita_rs

# Carregar .env logo no início para garantir que GEMINI_API_KEY esteja disponível
try:
	import dotenv
	_env_path = Path(__file__).resolve().parents[1] / ".env"
	if _env_path.exists():
		dotenv.load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
	pass

FIXTURE_CHAVE = "43251193015006003562651350005430861685582449"
FIXTURE_HTML = Path(__file__).resolve().parents[1] / ".github" / "xmlexemplo.xml"


def _item_para_classificacao() -> ItemParaClassificacao:
	return ItemParaClassificacao(
		chave_acesso=FIXTURE_CHAVE,
		sequencia=1,
		descricao="Arroz 5kg",
		codigo=None,
		quantidade=Decimal("1"),
		unidade="UN",
		valor_unitario=Decimal("20"),
		valor_total=Decimal("20"),
		categoria_sugerida=None,
		categoria_confirmada=None,
		emitente_nome="Mercado Teste",
		emissao_iso="2024-01-10T10:00:00",
	)


def _criar_mock_completion_response() -> Mock:
	"""Cria um mock de resposta do litellm.completion para testes."""
	conteudo_json = json.dumps({
		"itens": [{
			"sequencia": 1,
			"categoria": "Alimentação",
			"confianca": 0.9,
			"justificativa": "teste"
		}]
	})
	
	mock_response = Mock()
	mock_response.model_dump.return_value = {
		"choices": [
			{
				"message": {
					"content": conteudo_json
				}
			}
		]
	}
	return mock_response


def test_llm_classifier_interpreta_json_e_retorna_resultados():
	conteudo = {
		"choices": [
			{
				"message": {
					"content": json.dumps(
						{
							"itens": [
								{
									"sequencia": 1,
									"categoria": "Alimentação",
									"confianca": 0.88,
									"justificativa": "alimento básico",
									"produto": {
										"nome_base": "Arroz Integral",
										"marca_base": "Tio João",
									},
								}
							]
						}
					)
				}
			}
		]
	}

	def _fake_executar(self, payload, *, config, api_key):  # type: ignore[override]
		return conteudo["choices"][0]["message"]["content"], conteudo

	with patch.object(LLMClassifier, "_executar_chamada", _fake_executar):
		classifier = LLMClassifier(api_key="teste")
		itens = [_item_para_classificacao()]
		resultados = classifier.classificar_itens(itens)

	assert len(resultados) == 1
	resultado = resultados[0]
	assert resultado.categoria == "Alimentação"
	assert resultado.confianca == 0.88
	assert resultado.produto_nome == "Arroz Integral"
	assert resultado.produto_marca == "Tio João"
	assert resultado.modelo == classifier.model
	assert resultado.resposta_json is not None


def test_classificar_itens_pendentes_usa_registrar_classificacao(tmp_path):
	nota = receita_rs.parse_nota(FIXTURE_HTML.read_text(encoding="utf-8"), FIXTURE_CHAVE)
	_salvar_para_tmp(tmp_path, nota)

	class FakeLLM(LLMClassifier):  # type: ignore[misc]
		def __init__(self):  # pylint: disable=super-init-not-called
			self.chamadas = 0
			self.model = "fake"

		def classificar_itens(
			self,
			itens: Sequence[ItemParaClassificacao],
			*,
			model_priority=None,
			progress_callback=None,
		):
			self.chamadas += 1
			return [
				ClassificacaoResultado(
					chave_acesso=item.chave_acesso,
					sequencia=item.sequencia,
					categoria="alimentacao",
					confianca=0.7,
					modelo="fake",
					observacoes="teste",
					resposta_json="{}",
				)
				for item in itens
			]

	classificador = FakeLLM()
	resultados = classificar_itens_pendentes(
		classifier=cast(LLMClassifier, classificador),
		db_path=tmp_path / "tmp.db",
		limit=2,
		confirmar=True,
	)

	assert resultados
	assert classificador.chamadas == 1


def test_classificar_itens_pendentes_filtra_por_chave():
	with patch("src.classifiers.listar_itens_para_classificacao", return_value=[]) as mock_listar:
		resultados = classificar_itens_pendentes(chave_acesso="ABC123")
		assert resultados == []
		assert mock_listar.call_count == 1
		kwargs = mock_listar.call_args.kwargs
		assert kwargs["chave_acesso"] == "ABC123"


def test_llm_classifier_divide_requisicoes_em_chunks(monkeypatch):
	classifier = LLMClassifier(api_key="fake")
	itens: list[ItemParaClassificacao] = [
		ItemParaClassificacao(
			chave_acesso="123",
			sequencia=indice + 1,
			descricao=f"Item {indice + 1}",
			codigo=None,
			quantidade=Decimal("1"),
			unidade="UN",
			valor_unitario=Decimal("1.00"),
			valor_total=Decimal("1.00"),
			categoria_sugerida=None,
			categoria_confirmada=None,
			emitente_nome="Mercado",
			emissao_iso="2024-05-10T10:00:00",
		)
		for indice in range(MAX_ITENS_POR_CHAMADA + 5)
	]

	sequencias_por_bloco: list[list[int]] = []
	chamadas_executadas: list[int] = []

	def _fake_montar_payload(self, itens_chunk):  # type: ignore[override]
		sequencias_por_bloco.append([item.sequencia for item in itens_chunk])
		return {
			"model": self.model,
			"messages": [
				{"role": "system", "content": "teste"},
				{"role": "user", "content": "chunk"},
			],
		}

	def _fake_executar(self, payload, *, config, api_key):  # type: ignore[override]
		indice = len(chamadas_executadas)
		sequencias = sequencias_por_bloco[indice]
		conteudo = json.dumps(
			{"itens": [{"sequencia": seq, "categoria": "teste"} for seq in sequencias]}
		)
		chamadas_executadas.append(1)
		return conteudo, {"choices": [{"message": {"content": conteudo}}]}

	monkeypatch.setattr(LLMClassifier, "_montar_payload", _fake_montar_payload)
	monkeypatch.setattr(LLMClassifier, "_executar_chamada", _fake_executar)

	resultados = classifier.classificar_itens(itens)

	expected_chunks = (len(itens) + MAX_ITENS_POR_CHAMADA - 1) // MAX_ITENS_POR_CHAMADA
	assert len(sequencias_por_bloco) == expected_chunks
	assert len(chamadas_executadas) == expected_chunks
	assert all(len(chunk) <= MAX_ITENS_POR_CHAMADA for chunk in sequencias_por_bloco)
	assert len(resultados) == len(itens)


def test_executar_chamada_passa_extra_body_para_litellm():
	"""Testa que _executar_chamada passa extra_body para litellm.completion quando configurado."""
	# Criar uma configuração com extra_body
	config = ModeloConfig(
		nome="test/model",
		api_key_env="TEST_KEY",
		max_tokens=1000,
		max_itens=10,
		timeout=30.0,
		extra_body={"chat_template_kwargs": {"thinking": False}}
	)

	# Criar mock da resposta do litellm.completion com model_dump()
	mock_response = MagicMock()
	mock_response.model_dump.return_value = {
		"choices": [
			{
				"message": {
					"content": '{"itens": [{"sequencia": 1, "categoria": "teste"}]}'
				}
			}
		]
	}

	# Patchear litellm.completion
	with patch("src.classifiers.llm_classifier.completion", return_value=mock_response) as mock_completion:
		classifier = LLMClassifier(api_key="test_key", model="test/model")

		# Preparar payload de teste
		payload = {
			"model": "test/model",
			"messages": [{"role": "user", "content": "teste"}],
			"temperature": 0.1,
		}

		# Executar chamada
		classifier._executar_chamada(payload, config=config, api_key="test_key")

		# Verificar que completion foi chamado
		assert mock_completion.call_count == 1

		# Extrair argumentos da chamada
		call_args = mock_completion.call_args

		# Verificar argumentos explícitos
		assert call_args.kwargs["model"] == "test/model"
		assert call_args.kwargs["api_key"] == "test_key"
		assert call_args.kwargs["request_timeout"] == 30.0

		# Verificar que extra_body foi passado
		assert "extra_body" in call_args.kwargs
		assert call_args.kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": False}}


def test_executar_chamada_nao_passa_extra_body_quando_ausente():
	"""Testa que _executar_chamada não passa extra_body quando não está configurado."""
	# Criar uma configuração SEM extra_body
	config = ModeloConfig(
		nome="test/model",
		api_key_env="TEST_KEY",
		max_tokens=1000,
		max_itens=10,
		timeout=30.0,
		extra_body=None
	)

	# Criar mock da resposta do litellm.completion com model_dump()
	mock_response = MagicMock()
	mock_response.model_dump.return_value = {
		"choices": [
			{
				"message": {
					"content": '{"itens": [{"sequencia": 1, "categoria": "teste"}]}'
				}
			}
		]
	}

	# Patchear litellm.completion
	with patch("src.classifiers.llm_classifier.completion", return_value=mock_response) as mock_completion:
		classifier = LLMClassifier(api_key="test_key", model="test/model")

		# Preparar payload de teste
		payload = {
			"model": "test/model",
			"messages": [{"role": "user", "content": "teste"}],
			"temperature": 0.1,
		}

		# Executar chamada
		classifier._executar_chamada(payload, config=config, api_key="test_key")

		# Verificar que completion foi chamado
		assert mock_completion.call_count == 1

		# Extrair argumentos da chamada
		call_args = mock_completion.call_args

		# Verificar que extra_body NÃO foi passado
		assert "extra_body" not in call_args.kwargs


def _salvar_para_tmp(tmp_path, nota):
	# Helper para persistir nota no banco temporário durante o teste
	salvar_nota(nota, db_path=tmp_path / "tmp.db")


@pytest.mark.skipif(
	not os.getenv("GEMINI_API_KEY"),
	reason="GEMINI_API_KEY não configurada - teste de integração ignorado"
)
def test_llm_api_real_classifica_itens_e_retorna_json_valido():
	"""Teste de integração real com modelo Gemini via LiteLLM.

	Valida que:
	1. A API responde com sucesso
	2. O JSON retornado tem a estrutura esperada
	3. As categorias são extraídas corretamente
	4. A confiança está no formato esperado (0.0 a 1.0)
	"""
	classifier = LLMClassifier(model="gemini/gemini-2.5-pro", temperature=0.1)

	# Criar itens de teste com características distintas para classificação
	itens = [
		ItemParaClassificacao(
			chave_acesso="12345678901234567890123456789012345678901234",
			sequencia=1,
			descricao="ARROZ BRANCO TIPO 1 5KG",
			codigo="7891234567890",
			quantidade=Decimal("2"),
			unidade="UN",
			valor_unitario=Decimal("25.90"),
			valor_total=Decimal("51.80"),
			categoria_sugerida=None,
			categoria_confirmada=None,
			emitente_nome="SUPERMERCADO TESTE LTDA",
			emissao_iso="2025-11-20T14:30:00",
		),
		ItemParaClassificacao(
			chave_acesso="12345678901234567890123456789012345678901234",
			sequencia=2,
			descricao="DETERGENTE LIQUIDO 500ML",
			codigo="7891234567891",
			quantidade=Decimal("3"),
			unidade="UN",
			valor_unitario=Decimal("2.50"),
			valor_total=Decimal("7.50"),
			categoria_sugerida=None,
			categoria_confirmada=None,
			emitente_nome="SUPERMERCADO TESTE LTDA",
			emissao_iso="2025-11-20T14:30:00",
		),
		ItemParaClassificacao(
			chave_acesso="12345678901234567890123456789012345678901234",
			sequencia=3,
			descricao="SHAMPOO ANTICASPA 400ML",
			codigo="7891234567892",
			quantidade=Decimal("1"),
			unidade="UN",
			valor_unitario=Decimal("18.90"),
			valor_total=Decimal("18.90"),
			categoria_sugerida=None,
			categoria_confirmada=None,
			emitente_nome="SUPERMERCADO TESTE LTDA",
			emissao_iso="2025-11-20T14:30:00",
		),
	]

	# Executar classificação
	try:
		resultados = classifier.classificar_itens(itens)
	except RateLimitError as err:
		pytest.skip(f"Teste ignorado por limite de cota do Gemini: {err}")

	# Validações básicas
	assert resultados, "A API deve retornar resultados"
	assert len(resultados) > 0, "Deve classificar pelo menos um item"

	# Validar cada resultado
	for resultado in resultados:
		# Validar campos obrigatórios
		assert resultado.chave_acesso, "chave_acesso não pode ser vazia"
		assert resultado.sequencia > 0, "sequencia deve ser positiva"
		assert resultado.categoria, "categoria não pode ser vazia"
		assert resultado.origem == "gemini-litellm", "origem deve ser 'gemini-litellm'"
		assert resultado.modelo, "modelo deve estar preenchido"

		# Validar confiança (se presente)
		if resultado.confianca is not None:
			assert 0.0 <= resultado.confianca <= 1.0, \
				f"confiança deve estar entre 0 e 1, obtido: {resultado.confianca}"

		# Validar JSON de resposta
		assert resultado.resposta_json, "resposta_json deve estar presente"

		# Parsear e validar estrutura do JSON
		try:
			dados_resposta = json.loads(resultado.resposta_json)
			assert "payload" in dados_resposta, "JSON deve conter 'payload'"
			assert "resposta" in dados_resposta, "JSON deve conter 'resposta'"

			# Validar payload
			payload = dados_resposta["payload"]
			assert "model" in payload, "payload deve conter 'model'"
			assert "messages" in payload, "payload deve conter 'messages'"

			# Validar resposta da API
			resposta_api = dados_resposta["resposta"]
			assert "choices" in resposta_api, "resposta API deve conter 'choices'"

		except json.JSONDecodeError as e:
			pytest.fail(f"JSON de resposta inválido: {e}")

	# Validar categorias específicas esperadas (aproximadamente)
	categorias_encontradas = {r.categoria.lower() for r in resultados}

	# Pelo menos alguma categoria relacionada a alimentação/limpeza/higiene deve aparecer
	categorias_validas = {
		"alimentacao", "alimentação", "alimento", "comida",
		"limpeza", "higiene", "cuidados pessoais", "pessoal"
	}

	assert any(
		any(cat_valida in cat_encontrada for cat_valida in categorias_validas)
		for cat_encontrada in categorias_encontradas
	), f"Pelo menos uma categoria válida esperada, obtidas: {categorias_encontradas}"

	print(f"\n✅ Teste de integração passou com {len(resultados)} itens classificados:")
	for r in resultados:
		print(f"   Seq {r.sequencia}: {r.categoria} (confiança: {r.confianca})")


def test_extra_body_passado_para_litellm_quando_configurado():
	"""Testa que extra_body é passado para litellm.completion quando presente no config."""
	mock_response = _criar_mock_completion_response()
	
	# Patch do completion
	with patch("src.classifiers.llm_classifier.completion", return_value=mock_response) as mock_completion:
		# Criar classificador com modelo que tem extra_body
		classifier = LLMClassifier(model="nvidia_nim/moonshotai/kimi-k2.5", api_key="test-key")
		
		# Executar classificação
		item = _item_para_classificacao()
		classifier.classificar_itens([item])
		
		# Verificar que completion foi chamado
		assert mock_completion.called, "completion deveria ter sido chamado"
		
		# Obter os argumentos da chamada
		call_args = mock_completion.call_args
		assert call_args is not None, "completion deveria ter sido chamado com argumentos"
		
		# Verificar que extra_body foi passado
		assert "extra_body" in call_args.kwargs, "extra_body deveria estar nos kwargs"
		assert call_args.kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": False}}, \
			f"extra_body incorreto: {call_args.kwargs.get('extra_body')}"
		
		# Verificar que model foi passado explicitamente
		assert call_args.kwargs["model"] == "nvidia_nim/moonshotai/kimi-k2.5"


def test_extra_body_nao_passado_quando_nao_configurado():
	"""Testa que extra_body NÃO é passado para litellm.completion quando ausente no config."""
	mock_response = _criar_mock_completion_response()
	
	# Patch do completion
	with patch("src.classifiers.llm_classifier.completion", return_value=mock_response) as mock_completion:
		# Criar classificador com modelo SEM extra_body
		classifier = LLMClassifier(model="gemini/gemini-2.5-flash-lite", api_key="test-key")
		
		# Executar classificação
		item = _item_para_classificacao()
		classifier.classificar_itens([item])
		
		# Verificar que completion foi chamado
		assert mock_completion.called, "completion deveria ter sido chamado"
		
		# Obter os argumentos da chamada
		call_args = mock_completion.call_args
		assert call_args is not None, "completion deveria ter sido chamado com argumentos"
		
		# Verificar que extra_body NÃO foi passado
		assert "extra_body" not in call_args.kwargs, \
			f"extra_body não deveria estar nos kwargs, mas está: {call_args.kwargs.get('extra_body')}"
		
		# Verificar que model foi passado explicitamente
		assert call_args.kwargs["model"] == "gemini/gemini-2.5-flash-lite"
