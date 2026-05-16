from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List

import chromadb
from chromadb.api import ClientAPI
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

from src.logger import setup_logging

_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_CHROMA_COLLECTION_NAME = "produtos"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CHROMA_PERSIST_DIR = _PROJECT_ROOT / "data" / "chroma"
# Diretório persistente compartilhado entre execuções para cache dos modelos da Hugging Face.
_EMBEDDINGS_CACHE_DIR = _PROJECT_ROOT / "cache" / "huggingface"

_chroma_client: ClientAPI | None = None
_embedding_function: embedding_functions.EmbeddingFunction | None = None
_sentence_model: SentenceTransformer | None = None
# Double-checked locking mantém o fast path sem lock após a inicialização
# e evita a race condition de recriar singletons durante sessões simultâneas do Streamlit.
_client_lock = threading.Lock()
_embedding_function_lock = threading.Lock()
_sentence_model_lock = threading.Lock()


logger = setup_logging(__name__)


class ErroInicializacaoEmbeddings(RuntimeError):
    """Erro base para inicialização de embeddings."""


class ErroCacheEmbeddings(ErroInicializacaoEmbeddings):
    """Erro ao criar/acessar o cache local de embeddings."""


class ErroDownloadEmbeddings(ErroInicializacaoEmbeddings):
    """Erro ao baixar/carregar o modelo de embeddings."""


def obter_diretorio_cache_embeddings() -> Path:
    """Retorna o diretório persistente usado para cache dos modelos HF."""
    return _EMBEDDINGS_CACHE_DIR


def _configurar_variaveis_cache_embeddings() -> Path:
    cache_dir = obter_diretorio_cache_embeddings()
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErroCacheEmbeddings(
            f"Não foi possível criar/acessar diretório de cache de embeddings em '{cache_dir}'. "
            "Verifique permissões de escrita."
        ) from exc
    # Centraliza explicitamente o cache dos modelos HF no diretório de cache persistente
    for var in ("HF_HOME", "TRANSFORMERS_CACHE", "SENTENCE_TRANSFORMERS_HOME"):
        valor_atual = os.environ.get(var)
        if valor_atual and Path(valor_atual) != cache_dir:
            logger.warning(
                "Variável de ambiente %s já estava definida para '%s' e será "
                "sobrescrita para usar o cache persistente em '%s'.",
                var,
                valor_atual,
                cache_dir,
            )
        os.environ[var] = str(cache_dir)
    return cache_dir


def _definir_modo_offline(habilitado: bool) -> None:
    valor = "1" if habilitado else "0"
    os.environ["HF_HUB_OFFLINE"] = valor
    os.environ["TRANSFORMERS_OFFLINE"] = valor


def _carregar_sentence_transformer(*, cache_dir: Path, local_files_only: bool) -> SentenceTransformer:
    return SentenceTransformer(
        _EMBEDDING_MODEL_NAME,
        cache_folder=str(cache_dir),
        local_files_only=local_files_only,
    )


def inicializar_modelo_embeddings() -> SentenceTransformer:
    """Inicializa o modelo de embeddings usando cache local persistente."""
    global _sentence_model
    if _sentence_model is not None:
        return _sentence_model

    with _sentence_model_lock:
        if _sentence_model is not None:
            return _sentence_model

        cache_dir = _configurar_variaveis_cache_embeddings()
        try:
            _sentence_model = _carregar_sentence_transformer(
                cache_dir=cache_dir,
                local_files_only=True,
            )
            _definir_modo_offline(True)
            logger.info(
                "Modelo de embeddings carregado do cache local (%s).",
                cache_dir,
            )
            return _sentence_model
        except FileNotFoundError:
            _definir_modo_offline(False)
            logger.info(
                "Modelo de embeddings não encontrado localmente em %s. "
                "Tentando download inicial.",
                cache_dir,
            )
        except OSError as exc:
            _definir_modo_offline(False)
            mensagem = (
                "Falha ao acessar o cache local do modelo de embeddings em "
                f"'{cache_dir}'. Verifique permissões de escrita e leitura."
            )
            raise ErroCacheEmbeddings(mensagem) from exc
        except Exception:
            _definir_modo_offline(False)
            logger.exception(
                "Erro inesperado ao carregar modelo de embeddings do cache local em %s. "
                "Tentando download inicial.",
                cache_dir,
            )

        try:
            _sentence_model = _carregar_sentence_transformer(
                cache_dir=cache_dir,
                local_files_only=False,
            )
            _definir_modo_offline(True)
            logger.info(
                "Modelo de embeddings inicializado e armazenado em cache (%s).",
                cache_dir,
            )
            return _sentence_model
        except Exception as exc:
            if isinstance(exc, PermissionError):
                mensagem = (
                    "Falha ao inicializar o modelo de embeddings. "
                    "Verifique as permissões de escrita e acesso ao diretório de cache em "
                    f"'{cache_dir}'."
                )
                raise ErroCacheEmbeddings(mensagem) from exc

            mensagem = (
                "Falha ao inicializar o modelo de embeddings. "
                "Verifique sua conexão com a internet na primeira execução para permitir o "
                "download do modelo de embeddings."
            )
            raise ErroDownloadEmbeddings(mensagem) from exc


def _ensure_persist_dir() -> Path:
    _CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return _CHROMA_PERSIST_DIR


def _get_client() -> ClientAPI:
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    with _client_lock:
        if _chroma_client is not None:
            return _chroma_client

        persist_dir = _ensure_persist_dir()
        _chroma_client = chromadb.PersistentClient(path=str(persist_dir))
    return _chroma_client


def _get_embedding_function() -> embedding_functions.EmbeddingFunction:
    global _embedding_function
    if _embedding_function is not None:
        return _embedding_function

    with _embedding_function_lock:
        if _embedding_function is not None:
            return _embedding_function

        inicializar_modelo_embeddings()
        _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=_EMBEDDING_MODEL_NAME,
        )
    return _embedding_function


def _get_sentence_model() -> SentenceTransformer:
    return inicializar_modelo_embeddings()


def _get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=_CHROMA_COLLECTION_NAME,
        embedding_function=_get_embedding_function(),
    )


def gerar_embedding(texto: str) -> List[float]:
    if not texto:
        return []
    modelo = _get_sentence_model()
    return modelo.encode(texto, convert_to_numpy=True).tolist()


def upsert_produto_embedding(produto_id: int, descricao: str, nome_base: str | None = None, marca_base: str | None = None) -> None:
    """DEPRECATED: Usar upsert_descricao_embedding() ao invés desta função.

    Mantida apenas para compatibilidade com código legado.
    """
    upsert_descricao_embedding(
        descricao_original=descricao,
        nome_base=nome_base or "",
        marca_base=marca_base,
        categoria=None,
        produto_id=produto_id
    )


def upsert_descricao_embedding(
    descricao_original: str,
    nome_base: str,
    marca_base: str | None = None,
    categoria: str | None = None,
    produto_id: int | None = None
) -> None:
    """Indexa uma descrição original com seus dados padronizados.

    Args:
        descricao_original: Texto original da nota fiscal (ex: "CR LEITE PIRAC ZERO LAC 200G")
        nome_base: Nome padronizado do produto (ex: "Creme Leite Zero Lactose")
        marca_base: Marca do produto (ex: "Piracanjuba")
        categoria: Categoria validada (ex: "Laticínios e Frios")
        produto_id: ID opcional do produto na tabela produtos
    """
    texto = descricao_original.strip()
    if not texto:
        return

    if not nome_base or not nome_base.strip():
        return

    collection = _get_collection()
    embedding = gerar_embedding(texto)
    if not embedding:
        return

    # Usa hash da descrição normalizada como ID único
    import hashlib
    descricao_normalizada = texto.upper().strip()
    doc_id = hashlib.md5(descricao_normalizada.encode('utf-8')).hexdigest()

    metadata: Dict[str, Any] = {
        "descricao_original": texto,
        "nome_base": nome_base.strip(),
        "marca_base": marca_base.strip() if marca_base else "",
        "categoria": categoria.strip() if categoria else "",
        "produto_id": str(produto_id) if produto_id else "",
    }

    collection.upsert(
        ids=[doc_id],
        metadatas=[metadata],
        documents=[texto],
        embeddings=[embedding],
    )


def buscar_produtos_semelhantes(descricao: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Busca descrições similares já processadas anteriormente.

    Retorna lista com:
        - descricao_original: Texto original indexado
        - nome_base: Nome padronizado do produto
        - marca_base: Marca do produto
        - categoria: Categoria validada
        - produto_id: ID do produto (se disponível)
        - score: Similaridade (0.0 a 1.0)
    """
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

        # Extrai produto_id (pode ser string vazia)
        produto_id_str = metadata.get("produto_id", "")
        produto_id = None
        if produto_id_str and produto_id_str.strip():
            try:
                produto_id = int(produto_id_str)
            except (ValueError, TypeError):
                pass

        similaridades.append({
            "descricao_original": metadata.get("descricao_original", ""),
            "nome_base": metadata.get("nome_base", ""),
            "marca_base": metadata.get("marca_base", ""),
            "categoria": metadata.get("categoria", ""),
            "produto_id": produto_id,
            "score": similaridade,
        })
    return similaridades

def atualizar_produto_id_embeddings(produto_id_antigo: int, produto_id_novo: int) -> int:
    """Atualiza produto_id em embeddings após consolidação de produtos.

    Busca todos os embeddings com produto_id antigo e atualiza para o novo.
    Mantém todos os outros metadados intactos.

    Args:
        produto_id_antigo: ID do produto sendo consolidado
        produto_id_novo: ID do produto destino (mantido)

    Returns:
        Número de embeddings atualizados
    """
    try:
        collection = _get_collection()

        # Buscar embeddings com produto_id antigo (incluindo embeddings para evitar recálculo)
        resultados = collection.get(
            where={"produto_id": str(produto_id_antigo)},
            include=["embeddings", "metadatas", "documents"]
        )

        if not resultados or not resultados.get("ids"):
            logger.debug(f"Nenhum embedding encontrado para produto_id={produto_id_antigo}")
            return 0

        ids = resultados["ids"]
        metadatas = resultados.get("metadatas")
        if metadatas is None:
            metadatas = []
        documents = resultados.get("documents")
        if documents is None:
            documents = []
        embeddings = resultados.get("embeddings")  # Pode ser None ou numpy array

        if not ids:
            return 0

        # Validar consistência dos dados retornados
        if len(metadatas) != len(ids):
            logger.warning(
                f"Inconsistência: {len(ids)} IDs mas {len(metadatas)} metadatas. "
                f"Abortando atualização para produto_id={produto_id_antigo}"
            )
            return 0

        if len(documents) != len(ids):
            logger.warning(
                f"Inconsistência: {len(ids)} IDs mas {len(documents)} documents. "
                f"Abortando atualização para produto_id={produto_id_antigo}"
            )
            return 0

        # Atualizar metadata com novo produto_id
        for i in range(len(metadatas)):
            if metadatas[i] is None:
                metadatas[i] = {}
            metadatas[i]["produto_id"] = str(produto_id_novo)

        # Re-inserir com novo produto_id (upsert sobrescreve)
        # Construir argumentos do upsert condicionalmente
        upsert_args = {
            "ids": ids,
            "metadatas": metadatas,
            "documents": documents,
        }

        # Incluir embeddings apenas se disponível (ChromaDB pode não aceitar embeddings=None)
        if embeddings is not None:
            upsert_args["embeddings"] = embeddings

        collection.upsert(**upsert_args)

        logger.info(
            f"Embeddings atualizados: {len(ids)} registros migrados de "
            f"produto_id={produto_id_antigo} para produto_id={produto_id_novo}"
        )
        return len(ids)

    except Exception as exc:
        logger.exception(f"Erro ao atualizar produto_id em embeddings: {exc}")
        return 0
