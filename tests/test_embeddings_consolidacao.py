"""Testes para consolidação de embeddings (atualização de produto_id)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.classifiers.embeddings import (
    atualizar_produto_id_embeddings,
    upsert_descricao_embedding,
)


@pytest.fixture
def mock_chroma_client():
    """Mock do cliente ChromaDB para testes isolados."""
    with patch("src.classifiers.embeddings._get_collection") as mock_get_collection:
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        yield mock_collection


class TestAtualizarProdutoIdEmbeddings:
    """Testes para atualizar_produto_id_embeddings()."""

    def test_atualiza_embeddings_sucesso(self, mock_chroma_client, caplog):
        """Atualiza produto_id com sucesso quando há embeddings."""
        caplog.set_level("INFO", logger="src.classifiers.embeddings")

        # Simular resposta do ChromaDB com 2 embeddings
        mock_chroma_client.get.return_value = {
            "ids": ["hash1", "hash2"],
            "metadatas": [
                {
                    "descricao_original": "AGUA MINERAL 2L",
                    "nome_base": "Água Mineral",
                    "marca_base": "Crystal",
                    "categoria": "Bebidas",
                    "produto_id": "325",
                },
                {
                    "descricao_original": "AGUA C/GAS 2L",
                    "nome_base": "Água Mineral com Gás",
                    "marca_base": "Crystal",
                    "categoria": "Bebidas",
                    "produto_id": "325",
                },
            ],
            "documents": ["AGUA MINERAL 2L", "AGUA C/GAS 2L"],
            "embeddings": [[0.1] * 384, [0.2] * 384],
        }

        # Executar atualização
        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=325,
            produto_id_novo=40
        )

        # Verificar que buscou com filtro correto
        mock_chroma_client.get.assert_called_once_with(
            where={"produto_id": "325"},
            include=["embeddings", "metadatas", "documents"]
        )

        # Verificar que atualizou metadatas
        assert mock_chroma_client.upsert.called
        call_args = mock_chroma_client.upsert.call_args
        assert call_args.kwargs["ids"] == ["hash1", "hash2"]
        assert call_args.kwargs["metadatas"][0]["produto_id"] == "40"
        assert call_args.kwargs["metadatas"][1]["produto_id"] == "40"

        # Verificar retorno
        assert resultado == 2

        # Verificar logging de sucesso
        assert "Embeddings atualizados: 2 registros migrados" in caplog.text
        assert "produto_id=325" in caplog.text
        assert "produto_id=40" in caplog.text

    def test_nenhum_embedding_encontrado(self, mock_chroma_client, caplog):
        """Retorna 0 quando não há embeddings para o produto."""
        caplog.set_level("DEBUG", logger="src.classifiers.embeddings")

        # Simular ChromaDB sem resultados
        mock_chroma_client.get.return_value = {
            "ids": [],
            "metadatas": [],
            "documents": [],
            "embeddings": [],
        }

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=9999,
            produto_id_novo=40
        )

        # Não deve chamar upsert
        assert not mock_chroma_client.upsert.called

        # Retorna 0
        assert resultado == 0

        # Logging de debug
        assert "Nenhum embedding encontrado para produto_id=9999" in caplog.text

    def test_resultados_none(self, mock_chroma_client):
        """Trata resultados None do ChromaDB."""
        mock_chroma_client.get.return_value = None

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=100,
            produto_id_novo=200
        )

        assert resultado == 0
        assert not mock_chroma_client.upsert.called

    def test_ids_vazios(self, mock_chroma_client):
        """Trata lista de IDs vazia."""
        mock_chroma_client.get.return_value = {
            "ids": [],
        }

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=100,
            produto_id_novo=200
        )

        assert resultado == 0

    def test_inconsistencia_metadatas(self, mock_chroma_client, caplog):
        """Aborta quando há inconsistência entre IDs e metadatas."""
        caplog.set_level("WARNING", logger="src.classifiers.embeddings")

        # Simular ChromaDB retornando dados inconsistentes
        mock_chroma_client.get.return_value = {
            "ids": ["hash1", "hash2", "hash3"],  # 3 IDs
            "metadatas": [{"produto_id": "325"}],  # 1 metadata (ERRO!)
            "documents": ["AGUA MINERAL 2L"],
            "embeddings": [[0.1] * 384],
        }

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=325,
            produto_id_novo=40
        )

        # Não deve chamar upsert (abortado)
        assert not mock_chroma_client.upsert.called

        # Retorna 0
        assert resultado == 0

        # Logging de warning
        assert "Inconsistência: 3 IDs mas 1 metadatas" in caplog.text
        assert "Abortando atualização para produto_id=325" in caplog.text

    def test_metadata_none(self, mock_chroma_client):
        """Cria dict vazio quando metadata é None."""
        mock_chroma_client.get.return_value = {
            "ids": ["hash1"],
            "metadatas": [None],  # Metadata None
            "documents": ["AGUA MINERAL"],
            "embeddings": [[0.1] * 384],
        }

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=100,
            produto_id_novo=200
        )

        # Deve ter criado metadata com produto_id
        call_args = mock_chroma_client.upsert.call_args
        assert call_args.kwargs["metadatas"][0]["produto_id"] == "200"
        assert resultado == 1

    def test_preserva_outros_metadados(self, mock_chroma_client):
        """Preserva descricao_original, nome_base, etc."""
        mock_chroma_client.get.return_value = {
            "ids": ["hash1"],
            "metadatas": [
                {
                    "descricao_original": "LEITE PIRAC ZERO LAC",
                    "nome_base": "Leite Zero Lactose",
                    "marca_base": "Piracanjuba",
                    "categoria": "Laticínios",
                    "produto_id": "500",
                }
            ],
            "documents": ["LEITE PIRAC ZERO LAC"],
            "embeddings": [[0.3] * 384],
        }

        atualizar_produto_id_embeddings(
            produto_id_antigo=500,
            produto_id_novo=600
        )

        # Verificar que outros campos permaneceram intactos
        call_args = mock_chroma_client.upsert.call_args
        metadata_atualizada = call_args.kwargs["metadatas"][0]

        assert metadata_atualizada["descricao_original"] == "LEITE PIRAC ZERO LAC"
        assert metadata_atualizada["nome_base"] == "Leite Zero Lactose"
        assert metadata_atualizada["marca_base"] == "Piracanjuba"
        assert metadata_atualizada["categoria"] == "Laticínios"
        assert metadata_atualizada["produto_id"] == "600"  # Atualizado

    def test_embeddings_preservados(self, mock_chroma_client):
        """Embeddings originais são preservados (não recalculados)."""
        embedding_original = [0.123] * 384
        mock_chroma_client.get.return_value = {
            "ids": ["hash1"],
            "metadatas": [{"produto_id": "100"}],
            "documents": ["CHOCOLATE"],
            "embeddings": [embedding_original],
        }

        atualizar_produto_id_embeddings(
            produto_id_antigo=100,
            produto_id_novo=200
        )

        # Verificar que embeddings foram passados inalterados
        call_args = mock_chroma_client.upsert.call_args
        assert call_args.kwargs["embeddings"] == [embedding_original]

    def test_erro_chromadb_exception(self, mock_chroma_client, caplog):
        """Trata exceções do ChromaDB e retorna 0."""
        caplog.set_level("ERROR", logger="src.classifiers.embeddings")

        # Simular erro no ChromaDB
        mock_chroma_client.get.side_effect = Exception("ChromaDB connection failed")

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=100,
            produto_id_novo=200
        )

        # Deve retornar 0 sem propagar exceção
        assert resultado == 0

        # Deve logar o erro
        assert "Erro ao atualizar produto_id em embeddings" in caplog.text
        assert "ChromaDB connection failed" in caplog.text

    def test_erro_upsert_exception(self, mock_chroma_client, caplog):
        """Trata exceções durante upsert."""
        caplog.set_level("ERROR", logger="src.classifiers.embeddings")

        mock_chroma_client.get.return_value = {
            "ids": ["hash1"],
            "metadatas": [{"produto_id": "100"}],
            "documents": ["AGUA"],
            "embeddings": [[0.1] * 384],
        }

        # Simular erro no upsert
        mock_chroma_client.upsert.side_effect = Exception("Upsert failed")

        resultado = atualizar_produto_id_embeddings(
            produto_id_antigo=100,
            produto_id_novo=200
        )

        assert resultado == 0
        assert "Erro ao atualizar produto_id em embeddings" in caplog.text


class TestIntegracaoEmbeddingsConsolidacao:
    """Testes de integração com ChromaDB real."""

    def test_atualiza_embedding_real(self, tmp_path: Path):
        """Teste de integração com ChromaDB em diretório temporário."""
        # Configurar ChromaDB em diretório temporário
        chroma_dir = tmp_path / "chroma_test"
        chroma_dir.mkdir()

        with patch("src.classifiers.embeddings._CHROMA_PERSIST_DIR", chroma_dir):
            # Resetar cliente global para usar novo diretório
            import src.classifiers.embeddings as emb_module
            emb_module._chroma_client = None

            # 1. Inserir embedding com produto_id=100
            upsert_descricao_embedding(
                descricao_original="AGUA MINERAL CRYSTAL 2L",
                nome_base="Água Mineral",
                marca_base="Crystal",
                categoria="Bebidas",
                produto_id=100
            )

            # 2. Atualizar produto_id para 200
            resultado = atualizar_produto_id_embeddings(
                produto_id_antigo=100,
                produto_id_novo=200
            )

            # Verificar que 1 embedding foi atualizado
            assert resultado == 1

            # 3. Buscar e verificar que produto_id mudou
            from src.classifiers.embeddings import _get_collection
            collection = _get_collection()

            # Não deve haver embeddings com produto_id=100
            resultados_antigo = collection.get(where={"produto_id": "100"})
            assert len(resultados_antigo["ids"]) == 0

            # Deve haver 1 embedding com produto_id=200
            resultados_novo = collection.get(where={"produto_id": "200"})
            assert len(resultados_novo["ids"]) == 1
            assert resultados_novo["metadatas"][0]["produto_id"] == "200"
            assert resultados_novo["metadatas"][0]["nome_base"] == "Água Mineral"
            assert resultados_novo["metadatas"][0]["marca_base"] == "Crystal"

            # Cleanup
            emb_module._chroma_client = None

    def test_consolida_multiplos_embeddings(self, tmp_path: Path):
        """Consolida múltiplos embeddings de uma vez."""
        chroma_dir = tmp_path / "chroma_multi"
        chroma_dir.mkdir()

        with patch("src.classifiers.embeddings._CHROMA_PERSIST_DIR", chroma_dir):
            import src.classifiers.embeddings as emb_module
            emb_module._chroma_client = None

            # Inserir 3 embeddings com produto_id=325
            upsert_descricao_embedding(
                descricao_original="AGUA MINERAL 2L",
                nome_base="Água Mineral",
                marca_base="Crystal",
                categoria="Bebidas",
                produto_id=325
            )

            upsert_descricao_embedding(
                descricao_original="AGUA C/GAS 2L",
                nome_base="Água Mineral com Gás",
                marca_base="Crystal",
                categoria="Bebidas",
                produto_id=325
            )

            upsert_descricao_embedding(
                descricao_original="AGUA SEM GAS 2L",
                nome_base="Água Mineral sem Gás",
                marca_base="Crystal",
                categoria="Bebidas",
                produto_id=325
            )

            # Consolidar tudo para produto_id=40
            resultado = atualizar_produto_id_embeddings(
                produto_id_antigo=325,
                produto_id_novo=40
            )

            # Verificar que 3 embeddings foram atualizados
            assert resultado == 3

            # Verificar que todos agora têm produto_id=40
            from src.classifiers.embeddings import _get_collection
            collection = _get_collection()

            resultados_novo = collection.get(where={"produto_id": "40"})
            assert len(resultados_novo["ids"]) == 3

            # Não deve haver mais nada com produto_id=325
            resultados_antigo = collection.get(where={"produto_id": "325"})
            assert len(resultados_antigo["ids"]) == 0

            # Cleanup
            emb_module._chroma_client = None
