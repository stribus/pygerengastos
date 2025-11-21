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
         patch("src.classifiers.GroqClassifier") as MockGroq, \
         patch("src.classifiers._salvar_resultados") as mock_salvar:

        # Caso 1: Match semântico encontrado (> 0.82)
        mock_busca.return_value = [{
            "produto_id": 10,
            "nome_base": "Arroz",
            "marca_base": "Tio Joao",
            "score": 0.95
        }]
        
        classificar_itens_pendentes()
        
        # Verifica se NÃO chamou o Groq
        MockGroq.return_value.classificar_itens.assert_not_called()
        
        # Verifica se salvou com origem chroma-cache
        args, _ = mock_salvar.call_args
        resultados = args[0]
        assert len(resultados) == 1
        assert resultados[0].origem == "chroma-cache"
        assert resultados[0].categoria == "alimentacao"

def test_classificacao_fallback_groq():
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
         patch("src.classifiers.GroqClassifier") as MockGroq, \
         patch("src.classifiers._salvar_resultados"):

        # Configura retorno do Groq
        mock_groq_instance = MockGroq.return_value
        mock_groq_instance.classificar_itens.return_value = []

        classificar_itens_pendentes()
        
        # Verifica se CHAMOU o Groq
        mock_groq_instance.classificar_itens.assert_called_once()
