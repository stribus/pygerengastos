"""
Testes para carregamento de configuração de modelos LLM com:
- Lazy loading
- Background loading
- Cache thread-safe
- Tratamento de erros (TOML malformado, campos ausentes)
- Fallback para configuração hardcoded
"""

import concurrent.futures
import tempfile
import threading
import tomllib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.classifiers.llm_classifier import (
	ModeloConfig,
	_carregar_modelos_toml,
	_obter_modelos_fallback,
	iniciar_carregamento_background,
	obter_modelos_carregados,
	obter_modelos_disponiveis,
	recarregar_modelos,
)


@pytest.fixture(autouse=True)
def limpar_cache_modelos():
	"""Limpa cache de modelos antes e depois de cada teste."""
	import src.classifiers.llm_classifier as llm_module
	
	# Limpar antes
	with llm_module._modelos_cache_lock:
		llm_module._modelos_cache = None
	with llm_module._carregamento_lock:
		llm_module._carregamento_em_andamento = None
	
	yield
	
	# Limpar depois
	with llm_module._modelos_cache_lock:
		llm_module._modelos_cache = None
	with llm_module._carregamento_lock:
		llm_module._carregamento_em_andamento = None


def test_obter_modelos_fallback():
	"""Testa que fallback retorna configuração mínima válida do Gemini."""
	modelos = _obter_modelos_fallback()
	
	assert len(modelos) == 1
	modelo = modelos[0]
	
	assert modelo.nome == "gemini/gemini-2.5-flash-lite"
	assert modelo.api_key_env == "GEMINI_API_KEY"
	assert modelo.max_tokens == 8000
	assert modelo.max_itens == 50
	assert modelo.timeout == 30.0
	assert "Fallback" in modelo.nome_amigavel
	assert modelo.extra_body is None


def test_carregar_toml_arquivo_inexistente():
	"""Testa que arquivo inexistente retorna fallback."""
	with patch("src.classifiers.llm_classifier.CONFIG_FILE", Path("/tmp/arquivo_inexistente.toml")):
		modelos = _carregar_modelos_toml()
	
	# Deve retornar fallback
	assert len(modelos) == 1
	assert modelos[0].nome == "gemini/gemini-2.5-flash-lite"


def test_carregar_toml_sintaxe_invalida():
	"""Testa que TOML com sintaxe inválida retorna fallback."""
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		# TOML malformado: chave sem valor
		f.write("[[modelos]]\n")
		f.write("nome = \n")  # Sintaxe inválida
		f.write("api_key_env = 'KEY'\n")
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			modelos = _carregar_modelos_toml()
		
		# Deve retornar fallback
		assert len(modelos) == 1
		assert modelos[0].nome == "gemini/gemini-2.5-flash-lite"
	finally:
		temp_path.unlink()


def test_carregar_toml_campo_obrigatorio_ausente():
	"""Testa que modelo sem campo obrigatório é pulado mas outros são carregados."""
	toml_content = """
[[modelos]]
nome = "modelo_valido"
api_key_env = "KEY_VALIDA"
max_tokens = 4000

[[modelos]]
# Falta campo obrigatório 'api_key_env'
nome = "modelo_invalido"
max_tokens = 2000

[[modelos]]
# Falta campo obrigatório 'nome'
api_key_env = "OUTRA_KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			modelos = _carregar_modelos_toml()
		
		# Apenas o modelo válido deve ser carregado
		assert len(modelos) == 1
		assert modelos[0].nome == "modelo_valido"
		assert modelos[0].api_key_env == "KEY_VALIDA"
		assert modelos[0].max_tokens == 4000
	finally:
		temp_path.unlink()


def test_carregar_toml_todos_modelos_invalidos():
	"""Testa que se nenhum modelo for válido, retorna fallback."""
	toml_content = """
[[modelos]]
# Falta api_key_env
nome = "modelo1"

[[modelos]]
# Falta nome
api_key_env = "KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			modelos = _carregar_modelos_toml()
		
		# Deve retornar fallback
		assert len(modelos) == 1
		assert modelos[0].nome == "gemini/gemini-2.5-flash-lite"
	finally:
		temp_path.unlink()


def test_carregar_toml_com_extra_body():
	"""Testa que extra_body é carregado corretamente."""
	toml_content = """
[[modelos]]
nome = "test_model"
api_key_env = "TEST_KEY"
max_tokens = 8192

[modelos.extra_body.chat_template_kwargs]
thinking = false
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			modelos = _carregar_modelos_toml()
		
		assert len(modelos) == 1
		modelo = modelos[0]
		assert modelo.extra_body is not None
		assert modelo.extra_body["chat_template_kwargs"]["thinking"] is False
	finally:
		temp_path.unlink()


def test_carregar_toml_valores_default():
	"""Testa que valores default são aplicados quando campos opcionais estão ausentes."""
	toml_content = """
[[modelos]]
nome = "modelo_minimo"
api_key_env = "MIN_KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			modelos = _carregar_modelos_toml()
		
		assert len(modelos) == 1
		modelo = modelos[0]
		assert modelo.max_tokens == 8000  # DEFAULT_MAX_TOKENS
		assert modelo.max_itens == 50  # MAX_ITENS_POR_CHAMADA
		assert modelo.timeout == 30.0
		assert modelo.nome_amigavel is None
		assert modelo.extra_body is None
	finally:
		temp_path.unlink()


def test_iniciar_carregamento_background():
	"""Testa que carregamento em background retorna Future."""
	toml_content = """
[[modelos]]
nome = "test_model"
api_key_env = "TEST_KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			future = iniciar_carregamento_background()
		
		assert isinstance(future, concurrent.futures.Future)
		
		# Aguardar conclusão
		modelos = future.result(timeout=2.0)
		assert len(modelos) == 1
		assert modelos[0].nome == "test_model"
	finally:
		temp_path.unlink()


def test_iniciar_carregamento_background_reutiliza_future():
	"""Testa que múltiplas chamadas reutilizam o mesmo Future se ainda em andamento."""
	import src.classifiers.llm_classifier as llm_module
	
	toml_content = """
[[modelos]]
nome = "test_model"
api_key_env = "TEST_KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			# Criar um Future mock que simula carregamento lento
			with patch.object(llm_module, "_carregamento_em_andamento", None):
				future1 = iniciar_carregamento_background()
				future2 = iniciar_carregamento_background()
				
				# Devem ser o mesmo Future
				assert future1 is future2
	finally:
		temp_path.unlink()


def test_obter_modelos_carregados_aguarda_background():
	"""Testa que obter_modelos_carregados aguarda conclusão do background loading."""
	toml_content = """
[[modelos]]
nome = "bg_model"
api_key_env = "BG_KEY"
max_tokens = 4096
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			# Iniciar background loading
			iniciar_carregamento_background()
			
			# Obter modelos (deve aguardar)
			modelos = obter_modelos_carregados(aguardar=True)
			
			assert len(modelos) == 1
			assert modelos[0].nome == "bg_model"
			assert modelos[0].max_tokens == 4096
	finally:
		temp_path.unlink()


def test_obter_modelos_carregados_sem_aguardar_usa_fallback():
	"""Testa que obter_modelos_carregados retorna fallback se aguardar=False."""
	import src.classifiers.llm_classifier as llm_module
	import time
	
	def _slow_load():
		time.sleep(2)  # Simula carregamento lento
		return [ModeloConfig(
			nome="slow_model",
			api_key_env="SLOW_KEY",
			max_tokens=4000,
			max_itens=30,
			timeout=30.0
		)]
	
	with patch.object(llm_module, "_carregar_modelos_toml", side_effect=_slow_load):
		# Iniciar carregamento em background
		iniciar_carregamento_background()
		
		# Obter sem aguardar (deve usar fallback)
		modelos = obter_modelos_carregados(aguardar=False)
		
		# Deve ser fallback (Gemini)
		assert len(modelos) == 1
		assert modelos[0].nome == "gemini/gemini-2.5-flash-lite"


def test_obter_modelos_carregados_usa_cache():
	"""Testa que cache evita recarregamento desnecessário."""
	import src.classifiers.llm_classifier as llm_module
	
	toml_content = """
[[modelos]]
nome = "cached_model"
api_key_env = "CACHE_KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			# Primeira chamada: carrega do arquivo
			modelos1 = obter_modelos_carregados()
			
			# Segunda chamada: deve usar cache
			with patch.object(llm_module, "_carregar_modelos_toml") as mock_load:
				modelos2 = obter_modelos_carregados()
				
				# Não deve ter chamado _carregar_modelos_toml novamente
				mock_load.assert_not_called()
			
			# Devem ser os mesmos objetos
			assert modelos1 is modelos2
			assert len(modelos1) == 1
			assert modelos1[0].nome == "cached_model"
	finally:
		temp_path.unlink()


def test_recarregar_modelos_invalida_cache():
	"""Testa que recarregar_modelos() invalida cache e recarrega."""
	import src.classifiers.llm_classifier as llm_module
	
	toml_content_v1 = """
[[modelos]]
nome = "model_v1"
api_key_env = "KEY_V1"
"""
	
	toml_content_v2 = """
[[modelos]]
nome = "model_v2"
api_key_env = "KEY_V2"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content_v1)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			# Carregar v1
			modelos_v1 = obter_modelos_carregados()
			assert modelos_v1[0].nome == "model_v1"
			
			# Atualizar arquivo TOML
			with open(temp_path, "w") as f:
				f.write(toml_content_v2)
			
			# Recarregar
			modelos_v2 = recarregar_modelos()
			
			# Deve ter carregado nova versão
			assert modelos_v2[0].nome == "model_v2"
			
			# Cache deve estar atualizado
			modelos_v3 = obter_modelos_carregados()
			assert modelos_v3[0].nome == "model_v2"
	finally:
		temp_path.unlink()


def test_obter_modelos_disponiveis():
	"""Testa que obter_modelos_disponiveis retorna apenas os IDs."""
	toml_content = """
[[modelos]]
nome = "model_a"
api_key_env = "KEY_A"

[[modelos]]
nome = "model_b"
api_key_env = "KEY_B"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			# Limpar cache para forçar recarga
			import src.classifiers.llm_classifier as llm_module
			with llm_module._modelos_cache_lock:
				llm_module._modelos_cache = None
			
			ids = obter_modelos_disponiveis()
			
			assert ids == ["model_a", "model_b"]
	finally:
		temp_path.unlink()


def test_thread_safety_carregamento_concorrente():
	"""Testa que carregamento é thread-safe com múltiplas threads acessando simultaneamente."""
	import src.classifiers.llm_classifier as llm_module
	
	toml_content = """
[[modelos]]
nome = "concurrent_model"
api_key_env = "CONCURRENT_KEY"
"""
	
	with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
		f.write(toml_content)
		temp_path = Path(f.name)
	
	try:
		with patch("src.classifiers.llm_classifier.CONFIG_FILE", temp_path):
			resultados = []
			erros = []
			
			def _obter_modelos():
				try:
					modelos = obter_modelos_carregados()
					resultados.append(modelos)
				except Exception as e:
					erros.append(e)
			
			# Criar múltiplas threads
			threads = [threading.Thread(target=_obter_modelos) for _ in range(10)]
			
			# Iniciar todas
			for t in threads:
				t.start()
			
			# Aguardar todas
			for t in threads:
				t.join()
			
			# Não deve ter erros
			assert len(erros) == 0
			
			# Todas devem ter obtido modelos
			assert len(resultados) == 10
			
			# Todas devem ter o mesmo resultado (via cache)
			for modelos in resultados:
				assert len(modelos) == 1
				assert modelos[0].nome == "concurrent_model"
			
			# Verificar que todas são a mesma instância (cache funcionou)
			primeiro = resultados[0]
			for outros in resultados[1:]:
				assert outros is primeiro
	finally:
		temp_path.unlink()


def test_timeout_no_carregamento_background():
	"""Testa que timeout no background loading retorna fallback."""
	import src.classifiers.llm_classifier as llm_module
	import time
	
	def _very_slow_load():
		time.sleep(6)  # Levemente maior que BACKGROUND_LOAD_TIMEOUT (5s)
		return []
	
	with patch.object(llm_module, "_carregar_modelos_toml", side_effect=_very_slow_load):
		# Iniciar carregamento
		iniciar_carregamento_background()
		
		# Tentar obter (vai dar timeout após BACKGROUND_LOAD_TIMEOUT segundos)
		modelos = obter_modelos_carregados(aguardar=True)
		
		# Deve usar fallback
		assert len(modelos) == 1
		assert modelos[0].nome == "gemini/gemini-2.5-flash-lite"


def test_exception_no_carregamento_background():
	"""Testa que exceção no background loading retorna fallback."""
	import src.classifiers.llm_classifier as llm_module
	
	def _failing_load():
		raise RuntimeError("Erro simulado no carregamento")
	
	with patch.object(llm_module, "_carregar_modelos_toml", side_effect=_failing_load):
		# Iniciar carregamento
		iniciar_carregamento_background()
		
		# Tentar obter
		modelos = obter_modelos_carregados(aguardar=True)
		
		# Deve usar fallback
		assert len(modelos) == 1
		assert modelos[0].nome == "gemini/gemini-2.5-flash-lite"
