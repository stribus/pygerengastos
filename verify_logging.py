from src.logger import setup_logging
from src.database import inicializar_banco
import logging

def verify_logging():
    logger = setup_logging("test_logger")
    logger.info("Teste de log INFO")
    logger.debug("Teste de log DEBUG")
    logger.error("Teste de log ERROR")
    
    print("\nVerificando inicialização do banco com logs...")
    try:
        inicializar_banco()
        logger.info("Banco inicializado no teste.")
    except Exception as e:
        logger.error(f"Erro no teste de banco: {e}")

if __name__ == "__main__":
    verify_logging()
