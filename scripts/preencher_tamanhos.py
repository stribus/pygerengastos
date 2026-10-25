"""Pede à IA o tamanho da embalagem dos itens já gravados que não o têm.

Itens vendidos por unidade cuja descrição não traz o peso/volume ("CERVEJA
SPATEN PURO", truncada pelo mercado) ficam fora do preço por kg/litro dos
relatórios. As notas novas já recebem o tamanho na classificação; este script
cobre as antigas.

A IA recebe uma pergunta por descrição distinta e só responde quando tem
segurança. A resposta é gravada com origem "ia" para todos os itens com a
mesma descrição, como sugestão: ela só entra nos relatórios depois que você
confirmar os ajustes da nota na tela de análise (a IA às vezes chuta). O que
ela não souber fica para você preencher. Itens vendidos por KG/L e descrições com tamanho são ignorados.

Por padrão apenas lista as descrições sem tamanho, sem chamar a IA; use
--aplicar para consultar a IA e gravar. Faça backup de data/gastos.db antes.

Uso:
    python scripts/preencher_tamanhos.py [--aplicar] [--db CAMINHO]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Permite execução a partir da raiz do projeto sem necessidade de instalar o pacote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import DEFAULT_DB_PATH, ItemParaClassificacao, _aplicar_tamanho, conexao
from src.medidas import extrair_tamanho, normalizar_unidade


def _itens_sem_tamanho(con) -> list[ItemParaClassificacao]:
	"""Itens vendidos por unidade, sem tamanho na descrição nem informado."""
	rows = con.execute(
		"""
		SELECT chave_acesso, sequencia, descricao, unidade
		FROM itens
		WHERE tamanho IS NULL AND TRIM(COALESCE(descricao, '')) <> ''
		ORDER BY chave_acesso, sequencia
		"""
	).fetchall()
	return [
		ItemParaClassificacao(
			chave_acesso=chave, sequencia=sequencia, descricao=descricao, codigo=None,
			quantidade=None, unidade=unidade, valor_unitario=None, valor_total=None,
			categoria_sugerida=None, categoria_confirmada=None, emitente_nome=None, emissao_iso=None,
		)
		for chave, sequencia, descricao, unidade in rows
		if normalizar_unidade(unidade) not in ("KG", "L") and extrair_tamanho(descricao) is None
	]


def preencher(db_path: Path, *, aplicar: bool, classifier=None) -> dict[str, Any]:
	"""Lista (ou, com aplicar=True, preenche pela IA) os tamanhos que faltam. Retorna um relatório."""
	with conexao(db_path) as con:
		itens = _itens_sem_tamanho(con)

	# Um item por descrição: a resposta vale para todos os itens com a mesma descrição
	por_descricao: dict[str, ItemParaClassificacao] = {}
	for item in itens:
		por_descricao.setdefault(item.descricao.strip().upper(), item)
	relatorio: dict[str, Any] = {
		"descricoes": sorted(por_descricao),
		"itens": len(itens),
		"preenchidas": {},
		"sem_resposta": [],
	}
	if not aplicar or not por_descricao:
		return relatorio

	if classifier is None:
		from src.classifiers.llm_classifier import LLMClassifier

		classifier = LLMClassifier()
	tamanhos = classifier.sugerir_tamanhos(list(por_descricao.values()))

	with conexao(db_path) as con:
		for descricao, item in sorted(por_descricao.items()):
			tamanho = tamanhos.get((item.chave_acesso, item.sequencia))
			if tamanho:
				_aplicar_tamanho(con, item.chave_acesso, item.sequencia, tamanho, "ia")
				relatorio["preenchidas"][descricao] = tamanho
			else:
				relatorio["sem_resposta"].append(descricao)
	return relatorio


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--aplicar", action="store_true", help="consulta a IA e grava (padrão: só lista)")
	parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="banco SQLite")
	args = parser.parse_args()

	if not args.db.exists():
		print(f"ERRO: banco não encontrado: {args.db}", file=sys.stderr)
		sys.exit(1)

	relatorio = preencher(args.db, aplicar=args.aplicar)
	print(f"Itens sem tamanho: {relatorio['itens']} ({len(relatorio['descricoes'])} descrição(ões) distintas)")
	if not args.aplicar:
		for descricao in relatorio["descricoes"]:
			print(f"  {descricao}")
		print("\nSimulação: a IA não foi consultada e nada foi gravado. Use --aplicar (faça backup antes).")
		return

	print(f"\nSugeridas pela IA (confirme na tela de análise): {len(relatorio['preenchidas'])}")
	for descricao, tamanho in relatorio["preenchidas"].items():
		print(f"  {descricao}: {tamanho}")
	print(f"\nSem resposta (preencha na tela de análise): {len(relatorio['sem_resposta'])}")
	for descricao in relatorio["sem_resposta"]:
		print(f"  {descricao}")


if __name__ == "__main__":
	main()
