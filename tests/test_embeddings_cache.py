"""Testes para cache offline de embeddings."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.classifiers import embeddings


@pytest.fixture(autouse=True)
def limpar_estado_embeddings(monkeypatch):
    """Garante isolamento dos singletons de embeddings entre testes."""
    embeddings._sentence_model = None
    embeddings._embedding_function = None
    embeddings._chroma_client = None

    for variavel in (
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
    ):
        monkeypatch.delenv(variavel, raising=False)

    yield

    embeddings._sentence_model = None
    embeddings._embedding_function = None
    embeddings._chroma_client = None


def test_configura_variaveis_cache_embeddings(tmp_path, monkeypatch):
    cache_dir = tmp_path / "hf_cache"
    monkeypatch.setattr(embeddings, "_EMBEDDINGS_CACHE_DIR", cache_dir)

    resultado = embeddings._configurar_variaveis_cache_embeddings()

    assert resultado == cache_dir
    assert cache_dir.exists()
    assert os.environ["HF_HOME"] == str(cache_dir)
    assert os.environ["TRANSFORMERS_CACHE"] == str(cache_dir)
    assert os.environ["SENTENCE_TRANSFORMERS_HOME"] == str(cache_dir)


def test_inicializar_modelo_embeddings_reutiliza_cache_local(tmp_path, monkeypatch):
    cache_dir = tmp_path / "hf_cache"
    monkeypatch.setattr(embeddings, "_EMBEDDINGS_CACHE_DIR", cache_dir)

    chamadas: list[bool] = []
    modelo_esperado = object()

    def _fake_loader(*, cache_dir: Path, local_files_only: bool):
        chamadas.append(local_files_only)
        return modelo_esperado

    chamadas_offline: list[bool] = []
    definir_modo_offline_original = embeddings._definir_modo_offline

    def _spy_definir_modo_offline(habilitado: bool):
        chamadas_offline.append(habilitado)
        definir_modo_offline_original(habilitado)

    monkeypatch.setattr(embeddings, "_carregar_sentence_transformer", _fake_loader)
    monkeypatch.setattr(embeddings, "_definir_modo_offline", _spy_definir_modo_offline)

    modelo = embeddings.inicializar_modelo_embeddings()

    assert modelo is modelo_esperado
    assert cache_dir.exists()
    assert chamadas == [True]
    assert chamadas_offline == [True]
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_inicializar_modelo_embeddings_faz_fallback_para_download(tmp_path, monkeypatch):
    cache_dir = tmp_path / "hf_cache"
    monkeypatch.setattr(embeddings, "_EMBEDDINGS_CACHE_DIR", cache_dir)

    chamadas: list[bool] = []
    modelo_esperado = object()

    def _fake_loader(*, cache_dir: Path, local_files_only: bool):
        chamadas.append(local_files_only)
        if local_files_only:
            raise FileNotFoundError("cache local ausente")
        return modelo_esperado

    chamadas_offline: list[bool] = []
    definir_modo_offline_original = embeddings._definir_modo_offline

    def _spy_definir_modo_offline(habilitado: bool):
        chamadas_offline.append(habilitado)
        definir_modo_offline_original(habilitado)

    monkeypatch.setattr(embeddings, "_carregar_sentence_transformer", _fake_loader)
    monkeypatch.setattr(embeddings, "_definir_modo_offline", _spy_definir_modo_offline)

    modelo = embeddings.inicializar_modelo_embeddings()

    assert modelo is modelo_esperado
    assert chamadas == [True, False]
    assert chamadas_offline == [False, True]
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_inicializar_modelo_embeddings_erro_sem_cache_e_sem_internet(tmp_path, monkeypatch):
    cache_dir = tmp_path / "hf_cache"
    monkeypatch.setattr(embeddings, "_EMBEDDINGS_CACHE_DIR", cache_dir)

    def _fake_loader(*, cache_dir: Path, local_files_only: bool):
        raise OSError("sem rede")

    monkeypatch.setattr(embeddings, "_carregar_sentence_transformer", _fake_loader)

    with pytest.raises(embeddings.ErroDownloadEmbeddings) as exc_info:
        embeddings.inicializar_modelo_embeddings()

    assert cache_dir.exists()
    assert os.environ["HF_HUB_OFFLINE"] == "0"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "0"
    assert "Verifique sua conexão com a internet na primeira execução" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, OSError)


def test_inicializar_modelo_embeddings_erro_permissao_no_download(tmp_path, monkeypatch):
    cache_dir = tmp_path / "hf_cache"
    monkeypatch.setattr(embeddings, "_EMBEDDINGS_CACHE_DIR", cache_dir)

    def _fake_loader(*, cache_dir: Path, local_files_only: bool):
        if local_files_only:
            raise FileNotFoundError("cache local ausente")
        raise PermissionError("sem permissão")

    monkeypatch.setattr(embeddings, "_carregar_sentence_transformer", _fake_loader)

    with pytest.raises(embeddings.ErroCacheEmbeddings) as exc_info:
        embeddings.inicializar_modelo_embeddings()

    assert "Verifique as permissões de escrita" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, PermissionError)


def test_chroma_persistente_aponta_para_data_na_raiz():
    esperado = Path(__file__).resolve().parents[1] / "data" / "chroma"
    assert embeddings._CHROMA_PERSIST_DIR == esperado


def test_configurar_variaveis_cache_embeddings_levanta_erro_cache(monkeypatch):
    def _mkdir_falha(*args, **kwargs):
        raise PermissionError("sem permissão")

    monkeypatch.setattr(Path, "mkdir", _mkdir_falha)

    with pytest.raises(embeddings.ErroCacheEmbeddings) as exc_info:
        embeddings._configurar_variaveis_cache_embeddings()

    mensagem = str(exc_info.value)
    assert "cache de embeddings" in mensagem
    assert "Verifique permissões de escrita" in mensagem
