"""
Testes de validação de sintaxe TOML para configuração de modelos LLM.

Este módulo testa diferentes formas de definir sub-tabelas em arrays TOML,
especificamente para a configuração de extra_body nos modelos.
"""

import tomllib
import pytest


def test_sintaxe_subtabela_vs_inline_table():
    """
    Compara duas sintaxes TOML para definir extra_body:
    1. Sub-tabela (sintaxe atual): [modelos.extra_body.chat_template_kwargs]
    2. Inline table (sintaxe alternativa): extra_body = { ... }
    
    Ambas devem produzir a mesma estrutura de dados após parsing.
    """
    
    # Sintaxe 1: Sub-tabela (sintaxe atual no projeto)
    toml_subtabela = """
[[modelos]]
nome = "nvidia_nim/moonshotai/kimi-k2.5"
nome_amigavel = "Kimi K2.5 (Moonshot AI) teste1"
api_key_env = "NVIDIA_API_KEY"
max_tokens = 8192
max_itens = 25
timeout = 45.0

[modelos.extra_body.chat_template_kwargs]
thinking = false
"""
    
    # Sintaxe 2: Inline table (sintaxe proposta)
    toml_inline = """
[[modelos]]
nome = "nvidia_nim/moonshotai/kimi-k2.5"
nome_amigavel = "Kimi K2.5 (Moonshot AI) teste2"
api_key_env = "NVIDIA_API_KEY"
max_tokens = 8192
max_itens = 25
timeout = 45.0
extra_body = { chat_template_kwargs = { thinking = false } }
"""
    
    # Parse de ambas as strings
    data_subtabela = tomllib.loads(toml_subtabela)
    data_inline = tomllib.loads(toml_inline)
    
    # Validar que ambas têm 1 modelo
    assert len(data_subtabela["modelos"]) == 1
    assert len(data_inline["modelos"]) == 1
    
    # Extrair os modelos
    modelo_subtabela = data_subtabela["modelos"][0]
    modelo_inline = data_inline["modelos"][0]
    
    # Validar que ambos têm a estrutura extra_body
    assert "extra_body" in modelo_subtabela
    assert "extra_body" in modelo_inline
    
    # Validar que extra_body.chat_template_kwargs existe em ambos
    assert "chat_template_kwargs" in modelo_subtabela["extra_body"]
    assert "chat_template_kwargs" in modelo_inline["extra_body"]
    
    # Validar que thinking = false em ambos
    assert modelo_subtabela["extra_body"]["chat_template_kwargs"]["thinking"] is False
    assert modelo_inline["extra_body"]["chat_template_kwargs"]["thinking"] is False
    
    # Comparar as estruturas completas de extra_body
    assert modelo_subtabela["extra_body"] == modelo_inline["extra_body"]
    
    # Validar que outros campos também foram parseados corretamente
    assert modelo_subtabela["nome"] == "nvidia_nim/moonshotai/kimi-k2.5"
    assert modelo_inline["nome"] == "nvidia_nim/moonshotai/kimi-k2.5"
    assert modelo_subtabela["max_tokens"] == 8192
    assert modelo_inline["max_tokens"] == 8192


def test_multiplos_modelos_com_diferentes_sintaxes():
    """
    Testa um arquivo TOML com múltiplos modelos onde alguns usam
    sub-tabela e outros usam inline table.
    
    Este teste valida que é possível MIX de sintaxes em um mesmo arquivo.
    """
    
    toml_misto = """
# Modelo 1: sem extra_body
[[modelos]]
nome = "gemini/gemini-2.5-flash-lite"
nome_amigavel = "Gemini 2.5 Flash Lite"
api_key_env = "GEMINI_API_KEY"
max_tokens = 8000

# Modelo 2: com sub-tabela
[[modelos]]
nome = "nvidia_nim/moonshotai/kimi-k2.5"
nome_amigavel = "Kimi K2.5 (Sub-tabela)"
api_key_env = "NVIDIA_API_KEY"
max_tokens = 8192

[modelos.extra_body.chat_template_kwargs]
thinking = false

# Modelo 3: com inline table
[[modelos]]
nome = "nvidia_nim/meta/llama3-70b-instruct"
nome_amigavel = "LLaMA 3 (Inline)"
api_key_env = "NVIDIA_API_KEY"
max_tokens = 4096
extra_body = { chat_template_kwargs = { thinking = false } }
"""
    
    data = tomllib.loads(toml_misto)
    
    # Validar número de modelos
    assert len(data["modelos"]) == 3
    
    # Validar modelo 1 (sem extra_body)
    assert "extra_body" not in data["modelos"][0]
    
    # Validar modelo 2 (sub-tabela)
    assert data["modelos"][1]["extra_body"]["chat_template_kwargs"]["thinking"] is False
    
    # Validar modelo 3 (inline table)
    assert data["modelos"][2]["extra_body"]["chat_template_kwargs"]["thinking"] is False
    
    # Validar que modelos 2 e 3 têm a mesma estrutura de extra_body
    assert data["modelos"][1]["extra_body"] == data["modelos"][2]["extra_body"]


def test_arquivo_modelos_llm_atual():
    """
    Testa o arquivo real modelos_llm.toml do projeto para garantir
    que ele é parseável e tem a estrutura esperada.
    """
    
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "modelos_llm.toml"
    
    # Validar que o arquivo existe
    assert config_path.exists(), f"Arquivo não encontrado: {config_path}"
    
    # Parsear o arquivo
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    
    # Validar que tem modelos
    assert "modelos" in data
    assert len(data["modelos"]) > 0
    
    # Validar campos obrigatórios em cada modelo
    for idx, modelo in enumerate(data["modelos"]):
        assert "nome" in modelo, f"Modelo {idx} sem campo 'nome'"
        assert "nome_amigavel" in modelo, f"Modelo {idx} sem campo 'nome_amigavel'"
        assert "api_key_env" in modelo, f"Modelo {idx} sem campo 'api_key_env'"
        assert "max_tokens" in modelo, f"Modelo {idx} sem campo 'max_tokens'"
        
        # Se tem extra_body, validar estrutura
        if "extra_body" in modelo:
            assert isinstance(modelo["extra_body"], dict), \
                f"Modelo {idx}: extra_body deve ser um dicionário"


def test_sintaxe_subtabela_preserva_ordem():
    """
    Valida que a sintaxe de sub-tabela é associada ao modelo correto
    quando há múltiplos [[modelos]].
    
    IMPORTANTE: No TOML, [modelos.extra_body.chat_template_kwargs] após
    um [[modelos]] se aplica ao último modelo declarado.
    """
    
    toml_test = """
[[modelos]]
nome = "modelo_a"
api_key_env = "KEY_A"

[[modelos]]
nome = "modelo_b"
api_key_env = "KEY_B"

[modelos.extra_body.chat_template_kwargs]
thinking = false
"""
    
    data = tomllib.loads(toml_test)
    
    # O extra_body deve estar associado ao modelo_b (último modelo)
    assert "extra_body" not in data["modelos"][0]  # modelo_a não tem
    assert "extra_body" in data["modelos"][1]  # modelo_b tem
    assert data["modelos"][1]["extra_body"]["chat_template_kwargs"]["thinking"] is False


@pytest.mark.parametrize("thinking_value", [True, False])
def test_valores_booleanos_thinking(thinking_value):
    """
    Testa que valores booleanos true/false são parseados corretamente
    em ambas as sintaxes.
    """
    
    # Sub-tabela
    toml_subtabela = f"""
[[modelos]]
nome = "test_model"

[modelos.extra_body.chat_template_kwargs]
thinking = {str(thinking_value).lower()}
"""
    
    # Inline table
    toml_inline = f"""
[[modelos]]
nome = "test_model"
extra_body = {{ chat_template_kwargs = {{ thinking = {str(thinking_value).lower()} }} }}
"""
    
    data_subtabela = tomllib.loads(toml_subtabela)
    data_inline = tomllib.loads(toml_inline)
    
    # Validar que ambos têm o mesmo valor booleano
    assert data_subtabela["modelos"][0]["extra_body"]["chat_template_kwargs"]["thinking"] is thinking_value
    assert data_inline["modelos"][0]["extra_body"]["chat_template_kwargs"]["thinking"] is thinking_value
    
    # Validar que são realmente bool, não strings
    assert isinstance(
        data_subtabela["modelos"][0]["extra_body"]["chat_template_kwargs"]["thinking"], 
        bool
    )
    assert isinstance(
        data_inline["modelos"][0]["extra_body"]["chat_template_kwargs"]["thinking"], 
        bool
    )
