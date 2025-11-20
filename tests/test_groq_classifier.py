from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Sequence, cast
import json
import os

import httpx
import pytest

from src.classifiers import ClassificacaoResultado, classificar_itens_pendentes
from src.classifiers.groq import GroqClassifier
from src.database import ItemParaClassificacao, salvar_nota
from src.scrapers import receita_rs

# Carregar .env logo no início para garantir que GROQ_API_KEY esteja disponível
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


def test_groq_classifier_interpreta_json_e_retorna_resultados():
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
								}
							]
						}
					)
				}
			}
		]
	}
	transport = httpx.MockTransport(lambda request: httpx.Response(200, json=conteudo))
	client = httpx.Client(transport=transport)
	classifier = GroqClassifier(api_key="teste", client=client)
	itens = [_item_para_classificacao()]
	resultados = classifier.classificar_itens(itens)

	assert len(resultados) == 1
	resultado = resultados[0]
	assert resultado.categoria == "Alimentação"
	assert resultado.confianca == 0.88
	assert resultado.modelo == classifier.model
	assert resultado.resposta_json is not None
	client.close()


def test_classificar_itens_pendentes_usa_registrar_classificacao(tmp_path):
	nota = receita_rs.parse_nota(FIXTURE_HTML.read_text(encoding="utf-8"), FIXTURE_CHAVE)
	_salvar_para_tmp(tmp_path, nota)

	class FakeGroq(GroqClassifier):  # type: ignore[misc]
		def __init__(self):  # pylint: disable=super-init-not-called
			self.chamadas = 0
			self.model = "fake"

		def classificar_itens(self, itens: Sequence[ItemParaClassificacao]):
			self.chamadas += 1
			return [
				ClassificacaoResultado(
					chave_acesso=item.chave_acesso,
					sequencia=item.sequencia,
					categoria="alimentacao",
					confianca=0.7,
					origem="groq",
					modelo="fake",
					observacoes="teste",
					resposta_json="{}",
				)
				for item in itens
			]

	classificador = FakeGroq()
	resultados = classificar_itens_pendentes(
		classifier=cast(GroqClassifier, classificador),
		db_path=tmp_path / "tmp.duckdb",
		limit=2,
		confirmar=True,
	)

	assert resultados
	assert classificador.chamadas == 1


def _salvar_para_tmp(tmp_path, nota):
	# Helper para persistir nota no banco temporário durante o teste
	salvar_nota(nota, db_path=tmp_path / "tmp.duckdb")


@pytest.mark.skipif(
	not os.getenv("GROQ_API_KEY"),
	reason="GROQ_API_KEY não configurada - teste de integração ignorado"
)
def test_groq_api_real_classifica_itens_e_retorna_json_valido():
	"""Teste de integração real com API Groq.
	
	Valida que:
	1. A API responde com sucesso
	2. O JSON retornado tem a estrutura esperada
	3. As categorias são extraídas corretamente
	4. A confiança está no formato esperado (0.0 a 1.0)
	"""
	classifier = GroqClassifier(model="llama-3.1-8b-instant", temperature=0.1)
	
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
	resultados = classifier.classificar_itens(itens)
	
	# Validações básicas
	assert resultados, "A API deve retornar resultados"
	assert len(resultados) > 0, "Deve classificar pelo menos um item"
	
	# Validar cada resultado
	for resultado in resultados:
		# Validar campos obrigatórios
		assert resultado.chave_acesso, "chave_acesso não pode ser vazia"
		assert resultado.sequencia > 0, "sequencia deve ser positiva"
		assert resultado.categoria, "categoria não pode ser vazia"
		assert resultado.origem == "groq", "origem deve ser 'groq'"
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
