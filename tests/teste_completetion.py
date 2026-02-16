from openai import OpenAI

from litellm import completion
import os
from pathlib import Path
import dotenv


try:
	_env_path = Path(__file__).resolve().parents[1] / ".env"
	if _env_path.exists():
		dotenv.load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
	pass

# if os.getenv("NVIDIA_API_KEY") is None:
#     raise ValueError("NVIDIA_API_KEY environment variable not set.")

# # client = OpenAI(
# #   base_url = "https://integrate.api.nvidia.com/v1",
# #   api_key = os.getenv("NVIDIA_API_KEY")
# # )

# # completion = client.chat.completions.create(
# #   # model="deepseek-ai/deepseek-v3.2",
# #   model="moonshotai/kimi-k2.5",
# #   messages=[{"role": "system", "content": "Você é um classificador de itens de notas fiscais. Responda apenas com JSON válido."}, {"role": "user", "content": "Você classifica itens de notas fiscais em categorias de orçamento doméstico.\n\t\t\t\tEstabelecimento: COMPANHIA ZAFFARI COMERCIO E INDUSTRIA | Data: 2025-11-30T12:25:49\n\n\t\t\t\tCategorias disponíveis: Achocolatados, Alimentação Infantil, Amaciantes, Arroz, Aves (Frango/Peru), Açúcar e Adoçantes, Balas e Guloseimas, Barbear e Depilação, Biscoitos e Bolachas, Bolos e Tortas, Cabelo (Shampoo/Condicionador), Café e Chá, Carne Bovina, Carne Suína, Carnes para Churrasco, Cereais e Granola, Cervejas, Chocolates e Bombons, Coloração, Cuidados com a Pele, Descartáveis, Desinfetantes e Água Sanitária, Desodorantes, Destilados, Detergentes e Lava-louças, Embutidos (Linguiça/Salsicha), Energéticos e Isotônicos, Enlatados e Conservas, Ervas e Temperos Frescos, Farinhas e Grãos, Feijão e Leguminosas, Fraldas e Lenços, Frutas, Frutas Secas e Castanhas, Hambúrgueres, Higiene Bucal, Higiene Pet, Higiene Íntima, Iogurtes e Fermentados, Laticínios e Frios, Legumes, Leite e Substitutos, Limpadores Multiuso, Lâmpadas e Pilhas, Macarrão e Massas, Manteiga e Margarina, Mel e Geleias, Molhos e Condimentos, Ovos, Papel Higiênico e Papel Toalha, Peixes e Frutos do Mar, Pratos Prontos, Presunto e Apresuntados, Pães Frescos, Pães Industrializados, Queijos, Ração Cães, Ração Gatos, Refrigerantes, Requeijão e Cream Cheese, Sabonetes, Sabão para Roupas, Sal, Salgadinhos e Chips, Sobremesas, Sopas e Cremes, Sorvetes, Sucos e Néctares, Temperos Secos, Utensílios de Limpeza, Utilidades Domésticas, Vegetais Congelados, Verduras e Folhas, Vinhos e Espumantes, Água Mineral, Óleos e Azeites.\n\n\t\t\t\tINSTRUÇÕES:\n\t\t\t\t1. Use as categorias disponíveis \n\t\t\t\t2. Extraia nome e marca base do produto quando possível\n\t\t\t\t3. Seja objetivo nas justificativas (máx 5 palavras)\n\t\t\t\t4. Responda APENAS com JSON válido\n\n\t\t\t\tFORMATO DE RESPOSTA:\n\t\t\t\t{\n\t\t\t\t\t\"itens\": [\n\t\t\t\t\t\t{\"sequencia\": 1, \"categoria\": \"alimentacao\", \"confianca\": 0.84, \"produto\": {\"nome_base\": \"Arroz tipo 1\", \"marca_base\": \"Tio João\"}, \"justificativa\": \"alimento básico\"}\n\t\t\t\t\t]\n\t\t\t\t}\n\n\t\t\t\tITENS PARA CLASSIFICAR:\n\t\t\t\t- #1 — ESP TERRANOVA BRUT ROSE 750ML | quantidade: 2.00 UN \n- #2 — OLEO GIRASSOL SOYA 900ML | quantidade: 2.00 UN \n- #3 — AZ CAPELLINI EV 500ML | quantidade: 1.00 UN \n- #4 — VINAG MACA ROSANI 500ML | quantidade: 1.00 UN \n- #5 — OVO BRANCO EXTRA NATUROVOS C/30 | quantidade: 1.00 UN \n- #6 — ERVA MATE XIMANGO TRAD 1KG | quantidade: 2.00 UN \n- #7 — BISC ROSQ ZEZE CHOCOLATE 300G | quantidade: 1.00 UN \n- #8 — MASSA PENA URBANO ARROZ INT 500G | quantidade: 1.00 UN \n- #9 — AZ VERDE V.FERTIL C/C SH150G | quantidade: 1.00 UN \n- #10 — CAFE D.GUSTO ESPRESSO C/10 CAPS | quantidade: 1.00 UN \n- #11 — BISC CAMIL ARROZ/PIMENT INT 150G | quantidade: 1.00 UN \n- #12 — PIM REINO PT MERCATTO GR SH40G | quantidade: 1.00 UN \n- #13 — PEPINO PETRY SACHE 200G | quantidade: 1.00 UN \n- #14 — MASSA FETT ACACIAS INT 400G | quantidade: 1.00 UN \n- #15 — BISC ORQUIDEA INTEGRAL 53% 320G | quantidade: 1.00 UN \n- #16 — BISC JASM ARROZ ORIG INT S/G 90G | quantidade: 1.00 UN \n- #17 — CAFE 3CORAC TRADICIONAL VAC500G | quantidade: 1.00 UN \n- #18 — ZIMBRO TERRA RICA 25G | quantidade: 1.00 UN \n- #19 — IOG BATAVO P.ZERO MORANGO 1,15KG | quantidade: 1.00 UN \n- #20 — REQUEIJAO S.CLARA TRAD 400G | quantidade: 1.00 UN \n- #21 — MOLHO PIMENTA KIKKO 150ML | quantidade: 1.00 UN \n- #22 — RICOTA FRESCA LACMAX LIGHT 300G | quantidade: 1.00 UN \n- #23 — QJO COTTAGE V.CAMPO FRE Z.L 200G | quantidade: 1.00 UN \n- #24 — MILHO ODERICH 200G | quantidade: 4.00 UN \n- #25 — TOMATE S/PELE CAPELLINI     400G | quantidade: 2.00 UN \n- #26 — FUMACA LIQ AROMATIC DEF 150G | quantidade: 1.00 UN \n- #27 — MAIONESE HEINZ TRAD 400G | quantidade: 1.00 UN \n- #29 — CHA BARAO POS REFEICAO 10SH | quantidade: 2.00 UN \n- #30 — CHA BARAO CAMOMILA 10SH | quantidade: 1.00 UN \n- #31 — CREME AVEIA NUDE S/GL 200G | quantidade: 1.00 UN \n- #32 — CHA BARAO BOLDO 10SH | quantidade: 1.00 UN \n- #33 — CHA BARAO CAPIM CIDREIRA 10SH | quantidade: 1.00 UN \n- #34 — FILTRO PAPEL UTILO 102 C/30 | quantidade: 1.00 UN \n- #35 — UVA PASSA PT S/SEM KG | quantidade: 0.21 KG \n- #36 — NOZES PECAN EXTRA S/CASCA KG | quantidade: 0.11 KG \n- #37 — BIRI POMELO ZERO 1,25L | quantidade: 1.00 UN \n- #38 — COCA-COLA S/ACUCAR 600ML | quantidade: 1.00 UN \n- #39 — LIMAO TAITI GRANEL | quantidade: 0.81 KG \n- #40 — TOMATE REDINHA 1KG | quantidade: 1.00 UN \n- #41 — BANANA PRATA GRANEL | quantidade: 0.97 KG \n- #42 — CEBOLA BRANCA GRANEL | quantidade: 1.41 KG \n- #43 — PESSEGO BRANCO GAUCHO GRANEL | quantidade: 0.50 KG \n- #44 — CENOURA GRANEL | quantidade: 0.28 KG \n- #45 — MACA PINK IMPORTADA | quantidade: 0.45 KG \n- #46 — VAGEM MACARRAO GRANEL | quantidade: 0.17 KG \n- #47 — REPOLHO VERDE METADE AS | quantidade: 0.53 KG \n- #48 — BATATA BRANCA GRANEL | quantidade: 1.11 KG \n- #49 — ALFACE CRESPA ESTUFA | quantidade: 1.00 UN \n- #50 — RUCULA SUPER HIDROPONICA | quantidade: 1.00 UN \n- #51 — GRANULADO PIPICAT CLASSIC 4KG | quantidade: 5.00 UN"}],
# #   temperature=0.2,
# #   top_p=0.95,
# #   max_tokens=8192,
# #   extra_body={"chat_template_kwargs": {"thinking":False}},
# #   stream=False
# # )

# # # for chunk in completion:
# # #   if not getattr(chunk, "choices", None):
# # #     continue
# # #   reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
# # #   if reasoning:
# # #     print(reasoning, end="")
# # #   if chunk.choices and chunk.choices[0].delta.content is not None:
# # #     print(chunk.choices[0].delta.content, end="")


# # print(completion.choices[0].message.content)



nvidia_key = os.getenv("NVIDIA_API_KEY")
if nvidia_key is None:
    raise ValueError("NVIDIA_API_KEY environment variable not set.")
os.environ['NVIDIA_NIM_API_KEY'] = nvidia_key
response = completion(
    # model="nvidia_nim/meta/llama3-70b-instruct",
    model="nvidia_nim/moonshotai/kimi-k2.5",
    messages=[{"role": "system", "content": "Você é um classificador de itens de notas fiscais. Responda apenas com JSON válido."}, {"role": "user", "content": "Você classifica itens de notas fiscais em categorias de orçamento doméstico.\n\t\t\t\tEstabelecimento: COMPANHIA ZAFFARI COMERCIO E INDUSTRIA | Data: 2025-11-30T12:25:49\n\n\t\t\t\tCategorias disponíveis: Achocolatados, Alimentação Infantil, Amaciantes, Arroz, Aves (Frango/Peru), Açúcar e Adoçantes, Balas e Guloseimas, Barbear e Depilação, Biscoitos e Bolachas, Bolos e Tortas, Cabelo (Shampoo/Condicionador), Café e Chá, Carne Bovina, Carne Suína, Carnes para Churrasco, Cereais e Granola, Cervejas, Chocolates e Bombons, Coloração, Cuidados com a Pele, Descartáveis, Desinfetantes e Água Sanitária, Desodorantes, Destilados, Detergentes e Lava-louças, Embutidos (Linguiça/Salsicha), Energéticos e Isotônicos, Enlatados e Conservas, Ervas e Temperos Frescos, Farinhas e Grãos, Feijão e Leguminosas, Fraldas e Lenços, Frutas, Frutas Secas e Castanhas, Hambúrgueres, Higiene Bucal, Higiene Pet, Higiene Íntima, Iogurtes e Fermentados, Laticínios e Frios, Legumes, Leite e Substitutos, Limpadores Multiuso, Lâmpadas e Pilhas, Macarrão e Massas, Manteiga e Margarina, Mel e Geleias, Molhos e Condimentos, Ovos, Papel Higiênico e Papel Toalha, Peixes e Frutos do Mar, Pratos Prontos, Presunto e Apresuntados, Pães Frescos, Pães Industrializados, Queijos, Ração Cães, Ração Gatos, Refrigerantes, Requeijão e Cream Cheese, Sabonetes, Sabão para Roupas, Sal, Salgadinhos e Chips, Sobremesas, Sopas e Cremes, Sorvetes, Sucos e Néctares, Temperos Secos, Utensílios de Limpeza, Utilidades Domésticas, Vegetais Congelados, Verduras e Folhas, Vinhos e Espumantes, Água Mineral, Óleos e Azeites.\n\n\t\t\t\tINSTRUÇÕES:\n\t\t\t\t1. Use as categorias disponíveis \n\t\t\t\t2. Extraia nome e marca base do produto quando possível\n\t\t\t\t3. Seja objetivo nas justificativas (máx 5 palavras)\n\t\t\t\t4. Responda APENAS com JSON válido\n\n\t\t\t\tFORMATO DE RESPOSTA:\n\t\t\t\t{\n\t\t\t\t\t\"itens\": [\n\t\t\t\t\t\t{\"sequencia\": 1, \"categoria\": \"alimentacao\", \"confianca\": 0.84, \"produto\": {\"nome_base\": \"Arroz tipo 1\", \"marca_base\": \"Tio João\"}, \"justificativa\": \"alimento básico\"}\n\t\t\t\t\t]\n\t\t\t\t}\n\n\t\t\t\tITENS PARA CLASSIFICAR:\n\t\t\t\t- #1 — ESP TERRANOVA BRUT ROSE 750ML | quantidade: 2.00 UN \n- #2 — OLEO GIRASSOL SOYA 900ML | quantidade: 2.00 UN \n- #3 — AZ CAPELLINI EV 500ML | quantidade: 1.00 UN \n- #4 — VINAG MACA ROSANI 500ML | quantidade: 1.00 UN \n- #5 — OVO BRANCO EXTRA NATUROVOS C/30 | quantidade: 1.00 UN \n- #6 — ERVA MATE XIMANGO TRAD 1KG | quantidade: 2.00 UN \n- #7 — BISC ROSQ ZEZE CHOCOLATE 300G | quantidade: 1.00 UN \n- #8 — MASSA PENA URBANO ARROZ INT 500G | quantidade: 1.00 UN \n- #9 — AZ VERDE V.FERTIL C/C SH150G | quantidade: 1.00 UN \n- #10 — CAFE D.GUSTO ESPRESSO C/10 CAPS | quantidade: 1.00 UN \n- #11 — BISC CAMIL ARROZ/PIMENT INT 150G | quantidade: 1.00 UN \n- #12 — PIM REINO PT MERCATTO GR SH40G | quantidade: 1.00 UN \n- #13 — PEPINO PETRY SACHE 200G | quantidade: 1.00 UN \n- #14 — MASSA FETT ACACIAS INT 400G | quantidade: 1.00 UN \n- #15 — BISC ORQUIDEA INTEGRAL 53% 320G | quantidade: 1.00 UN \n- #16 — BISC JASM ARROZ ORIG INT S/G 90G | quantidade: 1.00 UN \n- #17 — CAFE 3CORAC TRADICIONAL VAC500G | quantidade: 1.00 UN \n- #18 — ZIMBRO TERRA RICA 25G | quantidade: 1.00 UN \n- #19 — IOG BATAVO P.ZERO MORANGO 1,15KG | quantidade: 1.00 UN \n- #20 — REQUEIJAO S.CLARA TRAD 400G | quantidade: 1.00 UN \n- #21 — MOLHO PIMENTA KIKKO 150ML | quantidade: 1.00 UN \n- #22 — RICOTA FRESCA LACMAX LIGHT 300G | quantidade: 1.00 UN \n- #23 — QJO COTTAGE V.CAMPO FRE Z.L 200G | quantidade: 1.00 UN \n- #24 — MILHO ODERICH 200G | quantidade: 4.00 UN \n- #25 — TOMATE S/PELE CAPELLINI     400G | quantidade: 2.00 UN \n- #26 — FUMACA LIQ AROMATIC DEF 150G | quantidade: 1.00 UN \n- #27 — MAIONESE HEINZ TRAD 400G | quantidade: 1.00 UN \n- #29 — CHA BARAO POS REFEICAO 10SH | quantidade: 2.00 UN \n- #30 — CHA BARAO CAMOMILA 10SH | quantidade: 1.00 UN \n- #31 — CREME AVEIA NUDE S/GL 200G | quantidade: 1.00 UN \n- #32 — CHA BARAO BOLDO 10SH | quantidade: 1.00 UN \n- #33 — CHA BARAO CAPIM CIDREIRA 10SH | quantidade: 1.00 UN \n- #34 — FILTRO PAPEL UTILO 102 C/30 | quantidade: 1.00 UN \n- #35 — UVA PASSA PT S/SEM KG | quantidade: 0.21 KG \n- #36 — NOZES PECAN EXTRA S/CASCA KG | quantidade: 0.11 KG \n- #37 — BIRI POMELO ZERO 1,25L | quantidade: 1.00 UN \n- #38 — COCA-COLA S/ACUCAR 600ML | quantidade: 1.00 UN \n- #39 — LIMAO TAITI GRANEL | quantidade: 0.81 KG \n- #40 — TOMATE REDINHA 1KG | quantidade: 1.00 UN \n- #41 — BANANA PRATA GRANEL | quantidade: 0.97 KG \n- #42 — CEBOLA BRANCA GRANEL | quantidade: 1.41 KG \n- #43 — PESSEGO BRANCO GAUCHO GRANEL | quantidade: 0.50 KG \n- #44 — CENOURA GRANEL | quantidade: 0.28 KG \n- #45 — MACA PINK IMPORTADA | quantidade: 0.45 KG \n- #46 — VAGEM MACARRAO GRANEL | quantidade: 0.17 KG \n- #47 — REPOLHO VERDE METADE AS | quantidade: 0.53 KG \n- #48 — BATATA BRANCA GRANEL | quantidade: 1.11 KG \n- #49 — ALFACE CRESPA ESTUFA | quantidade: 1.00 UN \n- #50 — RUCULA SUPER HIDROPONICA | quantidade: 1.00 UN \n- #51 — GRANULADO PIPICAT CLASSIC 4KG | quantidade: 5.00 UN"}],
    temperature=1,        # optional
    top_p=1,              # optional
    # frequency_penalty=0.1,  # optional
    # presence_penalty=0.1,   # optional
    max_tokens=8124,          # optional
    extra_body={"chat_template_kwargs": {"thinking": False}},
)
print(response)

print("----- USING REQUESTS -----")

import requests, base64

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
stream = False
nvidia_key = os.getenv("NVIDIA_API_KEY")
if nvidia_key is None:
    raise ValueError("NVIDIA_API_KEY environment variable not set.")

headers = {
  "Authorization": f"Bearer {nvidia_key}",
  "Accept": "text/event-stream" if stream else "application/json"
}

payload = {
  "model": "moonshotai/kimi-k2.5",
  "messages": [{"role":"user","content":"Você classifica itens de notas fiscais em categorias de orçamento doméstico.\\n\\t\\t\\t\\tEstabelecimento: COMPANHIA ZAFFARI COMERCIO E INDUSTRIA | Data: 2025-11-30T12:25:49\\n\\n\\t\\t\\t\\tCategorias disponíveis: Achocolatados, Alimentação Infantil, Amaciantes, Arroz, Aves (Frango/Peru), Açúcar e Adoçantes, Balas e Guloseimas, Barbear e Depilação, Biscoitos e Bolachas, Bolos e Tortas, Cabelo (Shampoo/Condicionador), Café e Chá, Carne Bovina, Carne Suína, Carnes para Churrasco, Cereais e Granola, Cervejas, Chocolates e Bombons, Coloração, Cuidados com a Pele, Descartáveis, Desinfetantes e Água Sanitária, Desodorantes, Destilados, Detergentes e Lava-louças, Embutidos (Linguiça/Salsicha), Energéticos e Isotônicos, Enlatados e Conservas, Ervas e Temperos Frescos, Farinhas e Grãos, Feijão e Leguminosas, Fraldas e Lenços, Frutas, Frutas Secas e Castanhas, Hambúrgueres, Higiene Bucal, Higiene Pet, Higiene Íntima, Iogurtes e Fermentados, Laticínios e Frios, Legumes, Leite e Substitutos, Limpadores Multiuso, Lâmpadas e Pilhas, Macarrão e Massas, Manteiga e Margarina, Mel e Geleias, Molhos e Condimentos, Ovos, Papel Higiênico e Papel Toalha, Peixes e Frutos do Mar, Pratos Prontos, Presunto e Apresuntados, Pães Frescos, Pães Industrializados, Queijos, Ração Cães, Ração Gatos, Refrigerantes, Requeijão e Cream Cheese, Sabonetes, Sabão para Roupas, Sal, Salgadinhos e Chips, Sobremesas, Sopas e Cremes, Sorvetes, Sucos e Néctares, Temperos Secos, Utensílios de Limpeza, Utilidades Domésticas, Vegetais Congelados, Verduras e Folhas, Vinhos e Espumantes, Água Mineral, Óleos e Azeites.\\n\\n\\t\\t\\t\\tINSTRUÇÕES:\\n\\t\\t\\t\\t1. Use as categorias disponíveis \\n\\t\\t\\t\\t2. Extraia nome e marca base do produto quando possível\\n\\t\\t\\t\\t3. Seja objetivo nas justificativas (máx 5 palavras)\\n\\t\\t\\t\\t4. Responda APENAS com JSON válido\\n\\n\\t\\t\\t\\tFORMATO DE RESPOSTA:\\n\\t\\t\\t\\t{\\n\\t\\t\\t\\t\\t\\\"itens\\\": [\\n\\t\\t\\t\\t\\t\\t{\\\"sequencia\\\": 1, \\\"categoria\\\": \\\"alimentacao\\\", \\\"confianca\\\": 0.84, \\\"produto\\\": {\\\"nome_base\\\": \\\"Arroz tipo 1\\\", \\\"marca_base\\\": \\\"Tio João\\\"}, \\\"justificativa\\\": \\\"alimento básico\\\"}\\n\\t\\t\\t\\t\\t]\\n\\t\\t\\t\\t}\\n\\n\\t\\t\\t\\tITENS PARA CLASSIFICAR:\\n\\t\\t\\t\\t- #1 — ESP TERRANOVA BRUT ROSE 750ML | quantidade: 2.00 UN \\n- #2 — OLEO GIRASSOL SOYA 900ML | quantidade: 2.00 UN \\n- #3 — AZ CAPELLINI EV 500ML | quantidade: 1.00 UN \\n- #4 — VINAG MACA ROSANI 500ML | quantidade: 1.00 UN \\n- #5 — OVO BRANCO EXTRA NATUROVOS C/30 | quantidade: 1.00 UN \\n- #6 — ERVA MATE XIMANGO TRAD 1KG | quantidade: 2.00 UN \\n- #7 — BISC ROSQ ZEZE CHOCOLATE 300G | quantidade: 1.00 UN \\n- #8 — MASSA PENA URBANO ARROZ INT 500G | quantidade: 1.00 UN \\n- #9 — AZ VERDE V.FERTIL C/C SH150G | quantidade: 1.00 UN \\n- #10 — CAFE D.GUSTO ESPRESSO C/10 CAPS | quantidade: 1.00 UN \\n- #11 — BISC CAMIL ARROZ/PIMENT INT 150G | quantidade: 1.00 UN \\n- #12 — PIM REINO PT MERCATTO GR SH40G | quantidade: 1.00 UN \\n- #13 — PEPINO PETRY SACHE 200G | quantidade: 1.00 UN \\n- #14 — MASSA FETT ACACIAS INT 400G | quantidade: 1.00 UN \\n- #15 — BISC ORQUIDEA INTEGRAL 53% 320G | quantidade: 1.00 UN \\n- #16 — BISC JASM ARROZ ORIG INT S/G 90G | quantidade: 1.00 UN \\n- #17 — CAFE 3CORAC TRADICIONAL VAC500G | quantidade: 1.00 UN \\n- #18 — ZIMBRO TERRA RICA 25G | quantidade: 1.00 UN \\n- #19 — IOG BATAVO P.ZERO MORANGO 1,15KG | quantidade: 1.00 UN \\n- #20 — REQUEIJAO S.CLARA TRAD 400G | quantidade: 1.00 UN \\n- #21 — MOLHO PIMENTA KIKKO 150ML | quantidade: 1.00 UN \\n- #22 — RICOTA FRESCA LACMAX LIGHT 300G | quantidade: 1.00 UN \\n- #23 — QJO COTTAGE V.CAMPO FRE Z.L 200G | quantidade: 1.00 UN \\n- #24 — MILHO ODERICH 200G | quantidade: 4.00 UN \\n- #25 — TOMATE S/PELE CAPELLINI     400G | quantidade: 2.00 UN \\n- #26 — FUMACA LIQ AROMATIC DEF 150G | quantidade: 1.00 UN \\n- #27 — MAIONESE HEINZ TRAD 400G | quantidade: 1.00 UN \\n- #29 — CHA BARAO POS REFEICAO 10SH | quantidade: 2.00 UN \\n- #30 — CHA BARAO CAMOMILA 10SH | quantidade: 1.00 UN \\n- #31 — CREME AVEIA NUDE S/GL 200G | quantidade: 1.00 UN \\n- #32 — CHA BARAO BOLDO 10SH | quantidade: 1.00 UN \\n- #33 — CHA BARAO CAPIM CIDREIRA 10SH | quantidade: 1.00 UN \\n- #34 — FILTRO PAPEL UTILO 102 C/30 | quantidade: 1.00 UN \\n- #35 — UVA PASSA PT S/SEM KG | quantidade: 0.21 KG \\n- #36 — NOZES PECAN EXTRA S/CASCA KG | quantidade: 0.11 KG \\n- #37 — BIRI POMELO ZERO 1,25L | quantidade: 1.00 UN \\n- #38 — COCA-COLA S/ACUCAR 600ML | quantidade: 1.00 UN \\n- #39 — LIMAO TAITI GRANEL | quantidade: 0.81 KG \\n- #40 — TOMATE REDINHA 1KG | quantidade: 1.00 UN \\n- #41 — BANANA PRATA GRANEL | quantidade: 0.97 KG \\n- #42 — CEBOLA BRANCA GRANEL | quantidade: 1.41 KG \\n- #43 — PESSEGO BRANCO GAUCHO GRANEL | quantidade: 0.50 KG \\n- #44 — CENOURA GRANEL | quantidade: 0.28 KG \\n- #45 — MACA PINK IMPORTADA | quantidade: 0.45 KG \\n- #46 — VAGEM MACARRAO GRANEL | quantidade: 0.17 KG \\n- #47 — REPOLHO VERDE METADE AS | quantidade: 0.53 KG \\n- #48 — BATATA BRANCA GRANEL | quantidade: 1.11 KG \\n- #49 — ALFACE CRESPA ESTUFA | quantidade: 1.00 UN \\n- #50 — RUCULA SUPER HIDROPONICA | quantidade: 1.00 UN \\n- #51 — GRANULADO PIPICAT CLASSIC 4KG | quantidade: 5.00 UN"}],
  "max_tokens": 16384,
  "temperature": 1.00,
  "top_p": 1.00,
  "stream": stream,
  "chat_template_kwargs": {"thinking":False},
}



response = requests.post(invoke_url, headers=headers, json=payload)

if stream:
    for line in response.iter_lines():
        if line:
            print(line.decode("utf-8"))
else:
    print(response.json())
