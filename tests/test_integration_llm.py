import os
import pytest
from decimal import Decimal
from litellm.exceptions import RateLimitError
from src.classifiers.llm_classifier import LLMClassifier, ModeloConfig
from src.database import ItemParaClassificacao

@pytest.mark.integration
def test_classifier_kimi_config_loading():
    """Verifica se a configuração do modelo Kimi carrega o extra_body corretamente."""
    classifier = LLMClassifier(model="nvidia_nim/moonshotai/kimi-k2.5")
    config = classifier._obter_config_modelo("nvidia_nim/moonshotai/kimi-k2.5")

    assert config.nome == "nvidia_nim/moonshotai/kimi-k2.5"
    assert config.extra_body is not None
    assert config.extra_body == {"chat_template_kwargs": {"thinking": False}}

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("NVIDIA_API_KEY"), reason="NVIDIA_API_KEY não configurada")
def test_classifier_kimi_integration():
    """Teste de integração real com a API do Kimi (NVIDIA NIM)."""

    # Criar classificador
    classifier = LLMClassifier(model="nvidia_nim/moonshotai/kimi-k2.5")

    # Criar item de teste com todos os campos obrigatórios
    item = ItemParaClassificacao(
        chave_acesso="TESTE123",
        sequencia=1,
        descricao="ESP TERRANOVA BRUT ROSE 750ML",
        codigo="12345",
        quantidade=Decimal("2.00"),
        unidade="UN",
        valor_unitario=Decimal("50.00"),
        valor_total=Decimal("100.00"),
        categoria_sugerida=None,
        categoria_confirmada=None,
        emitente_nome="COMPANHIA ZAFFARI",
        emissao_iso="2025-11-30T12:25:49"
    )

    # Executar classificação
    try:
        resultados = classifier.classificar_itens([item])
    except RateLimitError as err:
        pytest.skip(f"Teste ignorado por limite de cota da API NVIDIA: {err}")
    except Exception as err:
        # Captura timeouts e outros erros transientes da API
        erro_str = str(err).lower()
        if any(keyword in erro_str for keyword in ["timeout", "timed out", "connection", "unavailable"]):
            pytest.skip(f"Teste ignorado por erro transiente da API: {err}")
        # Re-raise se não for um erro transiente conhecido
        raise

    # Verificações
    assert len(resultados) == 1
    resultado = resultados[0]

    assert resultado.chave_acesso == "TESTE123"
    assert resultado.sequencia == 1
    assert resultado.modelo == "nvidia_nim/moonshotai/kimi-k2.5"
    assert resultado.categoria is not None
    # Verifica se a categoria retornada está na lista de categorias ou é uma string válida
    assert isinstance(resultado.categoria, str)
    assert len(resultado.categoria) > 0
