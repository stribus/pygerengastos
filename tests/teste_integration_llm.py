from src.classifiers.llm_classifier import LLMClassifier, ModeloConfig, ItemParaClassificacao
from src.database import ItemParaClassificacao
import os
from pathlib import Path
import dotenv

# Load .env
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
	dotenv.load_dotenv(dotenv_path=_env_path, override=False)

# Check keys
nvidia_key = os.getenv("NVIDIA_API_KEY")
print(f"NVIDIA_API_KEY present: {bool(nvidia_key)}")

# Create classifier with Kimi model
classifier = LLMClassifier(model="nvidia_nim/moonshotai/kimi-k2.5")

# Check config loaded correctly
config = classifier._obter_config_modelo("nvidia_nim/moonshotai/kimi-k2.5")
print(f"Config loaded for Kimi: {config}")
print(f"Extra body: {config.extra_body}")

# Create dummy item
item = ItemParaClassificacao(
    chave_acesso="12345",
    sequencia=1,
    descricao="ESP TERRANOVA BRUT ROSE 750ML",
    quantidade=2.0,
    unidade="UN",
    valor_total=100.0,
    emitente_nome="COMPANHIA ZAFFARI",
    emissao_iso="2025-11-30T12:25:49"
)

# Run classification
try:
    print("Starting classification...")
    resultados = classifier.classificar_itens([item])
    print("Classification finished!")
    for res in resultados:
        print(f"Result: {res}")
except Exception as e:
    print(f"Classification failed: {e}")
