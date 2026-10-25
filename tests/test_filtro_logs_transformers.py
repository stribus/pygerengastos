"""Testes do filtro de logs do transformers usado pelo app."""
from __future__ import annotations

import logging

import src.classifiers.embeddings  # noqa: F401  (registra o filtro ao importar)


def _mensagem_alias(nome: str) -> tuple[str, tuple[str, str, str]]:
	# Mesmo formato de transformers/__init__.py (aliases de compatibilidade *_fast)
	return (
		"Accessing `%s` from `%s`. Returning `%s` instead. Behavior may be "
		"different and this alias will be removed in future versions.",
		(nome, ".models.vit.image_processing_vit", nome),
	)


def test_aviso_de_alias_acessado_pelo_watcher_e_descartado(caplog):
	"""O watcher do Streamlit consulta __path__ em todo módulo; esse aviso não deve aparecer."""
	formato, args = _mensagem_alias("__path__")

	with caplog.at_level(logging.WARNING, logger="transformers"):
		logging.getLogger("transformers").warning(formato, *args)

	assert not [r for r in caplog.records if "Accessing `__path__`" in r.getMessage()]


def test_outros_avisos_do_transformers_continuam_visiveis(caplog):
	"""Só o acesso a __path__ é silenciado: uso real de classe *Fast e demais avisos aparecem."""
	formato, args = _mensagem_alias("ViTImageProcessorFast")

	with caplog.at_level(logging.WARNING, logger="transformers"):
		logging.getLogger("transformers").warning(formato, *args)
		logging.getLogger("transformers").warning("Some weights of the model were not initialized")

	mensagens = [r.getMessage() for r in caplog.records]
	assert any("ViTImageProcessorFast" in m for m in mensagens)
	assert any("Some weights" in m for m in mensagens)
