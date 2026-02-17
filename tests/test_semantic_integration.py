from unittest.mock import MagicMock, patch
from src.classifiers import classificar_itens_pendentes
from src.database import ItemParaClassificacao

def test_classificacao_semantica_prioritaria():
    # Mock dos itens pendentes
    mock_item = ItemParaClassificacao(
        chave_acesso="123",
        sequencia=1,
        descricao="ARROZ TIO JOAO",
        codigo="1",
        quantidade=1,
        unidade="UN",
        valor_unitario=10,
        valor_total=10,
        categoria_sugerida=None,
        categoria_confirmada=None,
        emitente_nome="MERCADO",
        emissao_iso="2023-01-01"
    )

    # Mock do banco de dados
    with patch("src.classifiers.listar_itens_para_classificacao", return_value=[mock_item]), \
         patch("src.classifiers.listar_categorias", return_value=[]), \
         patch("src.classifiers.obter_categoria_de_produto", return_value="alimentacao"), \
         patch("src.classifiers.buscar_produtos_semelhantes") as mock_busca, \
         patch("src.classifiers.LLMClassifier") as MockLLM, \
         patch("src.classifiers._salvar_resultados") as mock_salvar:

        # Caso 1: Match semântico encontrado (> 0.82)
        mock_busca.return_value = [{
            "produto_id": 10,
            "nome_base": "Arroz",
            "marca_base": "Tio Joao",
            "categoria": "alimentacao",
            "score": 0.95
        }]

        classificar_itens_pendentes()

        # Verifica se NÃO chamou o LLM
        MockLLM.return_value.classificar_itens.assert_not_called()

        # Verifica se salvou com origem chroma-cache
        args, _ = mock_salvar.call_args
        resultados = args[0]
        assert len(resultados) == 1
        assert resultados[0].origem == "chroma-cache"
        assert resultados[0].categoria == "alimentacao"

def test_classificacao_fallback_llm():
    # Mock dos itens pendentes
    mock_item = ItemParaClassificacao(
        chave_acesso="123",
        sequencia=1,
        descricao="PRODUTO NOVO",
        codigo="2",
        quantidade=1,
        unidade="UN",
        valor_unitario=10,
        valor_total=10,
        categoria_sugerida=None,
        categoria_confirmada=None,
        emitente_nome="MERCADO",
        emissao_iso="2023-01-01"
    )

    with patch("src.classifiers.listar_itens_para_classificacao", return_value=[mock_item]), \
         patch("src.classifiers.listar_categorias", return_value=[]), \
         patch("src.classifiers.buscar_produtos_semelhantes", return_value=[]), \
         patch("src.classifiers.LLMClassifier") as MockLLM, \
         patch("src.classifiers._salvar_resultados"):

        # Configura retorno do LLM
        mock_llm_instance = MockLLM.return_value
        mock_llm_instance.classificar_itens.return_value = []

        classificar_itens_pendentes()

        # Verifica se CHAMOU o LLM
        mock_llm_instance.classificar_itens.assert_called_once()


def test_forcar_llm_pula_busca_semantica():
    """Testa que forcar_llm=True pula completamente a busca semântica via Chroma."""
    mock_item = ItemParaClassificacao(
        chave_acesso="456",
        sequencia=1,
        descricao="ARROZ TIO JOAO",
        codigo="1",
        quantidade=1,
        unidade="UN",
        valor_unitario=10,
        valor_total=10,
        categoria_sugerida="alimentacao",
        categoria_confirmada="alimentacao",
        emitente_nome="MERCADO",
        emissao_iso="2023-01-01"
    )

    with patch("src.classifiers.listar_itens_para_classificacao", return_value=[mock_item]), \
         patch("src.classifiers.listar_categorias", return_value=[]), \
         patch("src.classifiers.limpar_classificacoes_completas", return_value=1) as mock_limpar, \
         patch("src.classifiers.buscar_produtos_semelhantes") as mock_busca, \
         patch("src.classifiers.LLMClassifier") as MockLLM, \
         patch("src.classifiers._salvar_resultados"):

        # Configura retorno do LLM
        mock_llm_instance = MockLLM.return_value
        mock_llm_instance.classificar_itens.return_value = []

        # Executa com forcar_llm=True
        classificar_itens_pendentes(
            forcar_llm=True,
            limpar_confirmadas_antes=True,
            chave_acesso="456",
            incluir_confirmados=True
        )

        # Verifica que limpou classificações completas
        mock_limpar.assert_called_once_with("456", db_path=None)

        # Verifica que NÃO chamou busca_produtos_semelhantes
        mock_busca.assert_not_called()

        # Verifica que CHAMOU o LLM diretamente
        mock_llm_instance.classificar_itens.assert_called_once()

