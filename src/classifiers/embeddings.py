from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from chromadb import Client
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_CHROMA_COLLECTION_NAME = "produtos"
_CHROMA_PERSIST_DIR = Path(__file__).resolve().parents[1] / "data" / "chroma"

_chroma_client: Optional[Client] = None
_embedding_function: Optional[embedding_functions.EmbeddingFunction] = None
_sentence_model: Optional[SentenceTransformer] = None


def _ensure_persist_dir() -> Path:
    _CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return _CHROMA_PERSIST_DIR


def _get_client() -> Client:
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    persist_dir = _ensure_persist_dir()
    settings = Settings(persist_directory=str(persist_dir), is_persistent=True)
    _chroma_client = Client(settings=settings)
    return _chroma_client


def _get_embedding_function() -> embedding_functions.EmbeddingFunction:
    global _embedding_function
    if _embedding_function is not None:
        return _embedding_function

    _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=_EMBEDDING_MODEL_NAME,
    )
    return _embedding_function


def _get_sentence_model() -> SentenceTransformer:
    global _sentence_model
    if _sentence_model is not None:
        return _sentence_model

    _sentence_model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _sentence_model


def _get_collection():
    client = _get_client()
    if _CHROMA_COLLECTION_NAME not in {col.name for col in client.list_collections()}:
        client.create_collection(
            name=_CHROMA_COLLECTION_NAME,
            embedding_function=_get_embedding_function(),
        )
    return client.get_collection(name=_CHROMA_COLLECTION_NAME)


def gerar_embedding(texto: str) -> List[float]:
    if not texto:
        return []
    modelo = _get_sentence_model()
    return modelo.encode(texto, convert_to_numpy=True).tolist()


def upsert_produto_embedding(produto_id: int, descricao: str, nome_base: str | None = None, marca_base: str | None = None) -> None:
    texto = descricao.strip()
    if not texto:
        return

    collection = _get_collection()
    embedding = gerar_embedding(texto)
    if not embedding:
        return

    metadata: Dict[str, Any] = {
        "produto_id": str(produto_id),
        "nome_base": nome_base or "",
        "marca_base": marca_base or "",
    }

    collection.upsert(
        ids=[str(produto_id)],
        metadatas=[metadata],
        documents=[texto],
        embeddings=[embedding],
    )


def buscar_produtos_semelhantes(descricao: str, top_k: int = 3) -> List[Dict[str, Any]]:
    texto = descricao.strip()
    if not texto:
        return []

    collection = _get_collection()
    resultados = collection.query(
        query_texts=[texto],
        n_results=top_k,
        include=["distances", "metadatas"],
    )

    similaridades: List[Dict[str, Any]] = []
    distancias = resultados.get("distances") or []
    metadatas = resultados.get("metadatas") or []
    if not distancias or not distancias[0]:
        return []

    linha_distancias = distancias[0]
    linha_metadatas = metadatas[0] if metadatas and metadatas[0] else [{} for _ in linha_distancias]
    for distancia, metadata in zip(linha_distancias, linha_metadatas):
        similaridade = max(0.0, 1.0 - distancia)
        similaridades.append({
            "produto_id": int(metadata.get("produto_id", 0)),
            "nome_base": metadata.get("nome_base", ""),
            "marca_base": metadata.get("marca_base", ""),
            "score": similaridade,
        })
    return similaridades
