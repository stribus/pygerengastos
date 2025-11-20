from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Sequence, cast
import json

import httpx

from src.classifiers import ClassificacaoResultado, classificar_itens_pendentes
from src.classifiers.groq import GroqClassifier
from src.database import ItemParaClassificacao, salvar_nota
from src.scrapers import receita_rs

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