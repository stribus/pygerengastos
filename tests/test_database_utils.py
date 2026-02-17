"""Testes para funções utilitárias do database."""
from pathlib import Path
from unittest.mock import patch

import pytest

from src.database import _resolver_caminho_banco


class TestResolverCaminhoBanco:
    """Testes para _resolver_caminho_banco()."""

    def test_caminho_padrao(self):
        """Retorna o caminho padrão quando db_path é None."""
        from src.database import DEFAULT_DB_PATH
        resultado = _resolver_caminho_banco(None)
        assert resultado == DEFAULT_DB_PATH

    def test_caminho_customizado(self, tmp_path: Path):
        """Retorna o caminho customizado quando fornecido."""
        custom_path = tmp_path / "meu_banco.db"
        resultado = _resolver_caminho_banco(custom_path)
        assert resultado == custom_path

    def test_cria_diretorio_pai(self, tmp_path: Path):
        """Cria o diretório pai se não existir."""
        # Criar um caminho onde o diretório pai não existe
        nested_path = tmp_path / "subdir1" / "subdir2" / "banco.db"

        # Verificar que o diretório pai não existe inicialmente
        assert not nested_path.parent.exists()

        # Chamar a função
        resultado = _resolver_caminho_banco(nested_path)

        # Verificar que o diretório pai foi criado
        assert nested_path.parent.exists()
        assert resultado == nested_path

    def test_nao_falha_se_diretorio_existe(self, tmp_path: Path):
        """Não falha se o diretório pai já existir."""
        # Criar diretório manualmente
        existing_dir = tmp_path / "existing_dir"
        existing_dir.mkdir()

        db_path = existing_dir / "banco.db"
        resultado = _resolver_caminho_banco(db_path)

        # Deve funcionar normalmente
        assert resultado == db_path
        assert existing_dir.exists()

    def test_converte_string_para_path(self, tmp_path: Path):
        """Converte string para Path automaticamente."""
        db_path_str = str(tmp_path / "banco.db")
        resultado = _resolver_caminho_banco(db_path_str)

        assert isinstance(resultado, Path)
        assert resultado == Path(db_path_str)

    def test_caminho_absoluto(self, tmp_path: Path):
        """Funciona com caminhos absolutos."""
        abs_path = tmp_path / "abs" / "banco.db"
        resultado = _resolver_caminho_banco(abs_path)

        assert resultado.is_absolute()
        assert resultado.parent.exists()

    def test_caminho_relativo(self, tmp_path: Path):
        """Funciona com caminhos relativos."""
        # Mudar para o diretório temporário
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            rel_path = Path("rel") / "banco.db"
            resultado = _resolver_caminho_banco(rel_path)

            assert resultado.parent.exists()
            assert resultado.name == "banco.db"
        finally:
            os.chdir(old_cwd)