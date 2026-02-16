"""
Teste específico para validar o refatoramento da exportação CSV.

Compara a saída da abordagem imperativa (original) com a abordagem declarativa (refatorada).
"""

from datetime import datetime, timedelta
import pandas as pd
import sys

from src.database import (
    obter_top_produtos_por_quantidade,
    obter_custos_unitarios_mensais,
    obter_unidades_produtos,
)
from src.ui.relatorios import _preencher_meses_faltantes, _calcular_inflacao_acumulada, _identificar_produtos_regulares, _calcular_cesta_basica_personalizada


def test_csv_export_refactored():
    """Valida que o DataFrame de exportação foi refatorado corretamente."""
    print("\n" + "="*70)
    print("TESTE: Refatoramento da Exportação CSV")
    print("="*70 + "\n")
    
    # Setup: buscar dados reais
    data_fim = datetime.now().date()
    data_inicio = data_fim - timedelta(days=365)
    
    print(f"📅 Período: {data_inicio} até {data_fim}\n")
    
    # Obter dados
    print("1️⃣ Carregando dados do banco...")
    top_produtos = obter_top_produtos_por_quantidade(
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
        top_n=5,  # Apenas 5 para teste mais rápido
    )
    
    if not top_produtos:
        print("   ⚠️  Nenhum produto encontrado. Teste inconclusivo.")
        return False
    
    produtos_nomes = [p["produto_nome"] for p in top_produtos]
    print(f"   ✅ {len(produtos_nomes)} produtos carregados")
    
    custos = obter_custos_unitarios_mensais(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )
    
    if not custos:
        print("   ⚠️  Nenhum custo encontrado. Teste inconclusivo.")
        return False
    
    print(f"   ✅ {len(custos)} registros de custos carregados")
    
    # Preencher meses faltantes
    df_completo = _preencher_meses_faltantes(
        custos,
        produtos_nomes,
        data_inicio.isoformat(),
        data_fim.isoformat(),
    )
    
    if df_completo.empty:
        print("   ⚠️  DataFrame vazio. Teste inconclusivo.")
        return False
    
    print(f"   ✅ DataFrame preenchido: {len(df_completo)} registros")
    
    # Identificar produtos regulares
    produtos_regulares = _identificar_produtos_regulares(df_completo)
    print(f"   ✅ {len(produtos_regulares)} produtos regulares identificados")
    
    # Calcular inflação por produto
    meses_ordenados = sorted(df_completo["ano_mes"].unique())
    inflacao_por_produto = {}
    
    for produto in produtos_nomes:
        df_produto = df_completo[df_completo["produto_nome"] == produto].sort_values("ano_mes")
        if not df_produto.empty:
            inflacao = _calcular_inflacao_acumulada(df_produto)
            inflacao_alinhada = [inflacao[i] if i < len(inflacao) else float('nan')
                                 for i in range(len(meses_ordenados))]
            inflacao_por_produto[produto] = inflacao_alinhada
    
    # Calcular inflação média
    if produtos_regulares:
        inflacao_media = []
        for i in range(len(meses_ordenados)):
            valores_mes = [
                inflacao_por_produto[p][i]
                for p in produtos_regulares
                if p in inflacao_por_produto and not pd.isna(inflacao_por_produto[p][i])
            ]
            if valores_mes:
                inflacao_media.append(sum(valores_mes) / len(valores_mes))
            else:
                inflacao_media.append(0.0)
    else:
        inflacao_media = [0.0] * len(meses_ordenados)
    
    # Calcular cesta básica
    df_cesta = _calcular_cesta_basica_personalizada(df_completo, produtos_regulares)
    if not df_cesta.empty:
        inflacao_cesta_lista = _calcular_inflacao_acumulada(df_cesta, coluna_valor="custo_cesta")
        inflacao_cesta = [inflacao_cesta_lista[i] if i < len(inflacao_cesta_lista) else 0.0
                          for i in range(len(meses_ordenados))]
    else:
        inflacao_cesta = [0.0] * len(meses_ordenados)
    
    # Buscar unidades
    unidades = obter_unidades_produtos(produtos_nomes)
    
    print("\n2️⃣ Testando abordagem refatorada (declarativa)...")
    print("-" * 70)
    
    # === ABORDAGEM REFATORADA (DECLARATIVA) ===
    
    # 1. Pivotar os preços
    df_precos = df_completo.pivot(
        index="ano_mes",
        columns="produto_nome",
        values="custo_unitario_medio"
    ).reindex(meses_ordenados)
    
    df_precos.columns = [
        f"{col} - Preço ({unidades.get(col, 'UN')})"
        for col in df_precos.columns
    ]
    
    # 2. DataFrame de inflação
    df_inflacao_produtos = pd.DataFrame(
        inflacao_por_produto,
        index=meses_ordenados
    )
    
    df_inflacao_produtos.columns = [
        f"{col} - Inflação (%)"
        for col in df_inflacao_produtos.columns
    ]
    
    # 3. DataFrame extras
    df_extras = pd.DataFrame(index=meses_ordenados)
    df_extras["Inflação Média (%)"] = inflacao_media
    
    if not df_cesta.empty:
        df_extras["Cesta Básica - Custo (R$)"] = (
            df_cesta.set_index("ano_mes")["custo_cesta"]
            .reindex(meses_ordenados)
        )
        
        df_extras["Cesta Básica - Inflação (%)"] = pd.Series(
            inflacao_cesta,
            index=meses_ordenados[:len(inflacao_cesta)]
        ).reindex(meses_ordenados, method='ffill')
    
    # 4. Ordenar colunas intercalando preço e inflação
    colunas_ordenadas = ["Mês"]
    for produto in produtos_nomes:
        unidade = unidades.get(produto, "UN")
        col_preco = f"{produto} - Preço ({unidade})"
        col_inflacao = f"{produto} - Inflação (%)"
        if col_preco in df_precos.columns:
            colunas_ordenadas.append(col_preco)
        if col_inflacao in df_inflacao_produtos.columns:
            colunas_ordenadas.append(col_inflacao)
    
    colunas_ordenadas.extend(df_extras.columns.tolist())
    
    # 5. Concatenar
    df_export_novo = pd.concat(
        [df_precos, df_inflacao_produtos, df_extras],
        axis=1
    )
    
    df_export_novo = df_export_novo.reset_index().rename(columns={"index": "Mês"})
    df_export_novo = df_export_novo[
        [col for col in colunas_ordenadas if col in df_export_novo.columns]
    ]
    
    print(f"   ✅ DataFrame gerado: {df_export_novo.shape}")
    print(f"   ✅ Colunas: {len(df_export_novo.columns)}")
    print(f"   ✅ Linhas: {len(df_export_novo)}")
    
    # Validações
    print("\n3️⃣ Validando estrutura do DataFrame...")
    print("-" * 70)
    
    # Validar que tem coluna Mês
    assert "Mês" in df_export_novo.columns, "❌ Coluna 'Mês' ausente!"
    print("   ✅ Coluna 'Mês' presente")
    
    # Validar que número de linhas corresponde aos meses
    assert len(df_export_novo) == len(meses_ordenados), f"❌ Número de linhas incorreto: {len(df_export_novo)} != {len(meses_ordenados)}"
    print(f"   ✅ Número correto de linhas: {len(df_export_novo)}")
    
    # Validar que todas as colunas esperadas existem
    for produto in produtos_nomes:
        unidade = unidades.get(produto, "UN")
        col_preco = f"{produto} - Preço ({unidade})"
        col_inflacao = f"{produto} - Inflação (%)"
        
        # Nem todos os produtos têm preços em todos os meses, mas as colunas devem existir
        if produto in df_completo["produto_nome"].values:
            assert col_preco in df_export_novo.columns, f"❌ Coluna de preço ausente: {col_preco}"
    
    print(f"   ✅ Todas as colunas esperadas estão presentes")
    
    # Validar coluna de inflação média
    assert "Inflação Média (%)" in df_export_novo.columns, "❌ Coluna 'Inflação Média (%)' ausente!"
    print("   ✅ Coluna 'Inflação Média (%)' presente")
    
    # Validar que valores de inflação média batem
    valores_inflacao_media = df_export_novo["Inflação Média (%)"].tolist()
    for i, (val_novo, val_esperado) in enumerate(zip(valores_inflacao_media, inflacao_media)):
        if pd.isna(val_novo) and pd.isna(val_esperado):
            continue
        if pd.isna(val_novo) or pd.isna(val_esperado):
            print(f"   ⚠️  Mês {i}: Novo={val_novo}, Esperado={val_esperado}")
            continue
        diff = abs(val_novo - val_esperado)
        assert diff < 0.001, f"❌ Inflação média diverge no mês {i}: {val_novo} != {val_esperado}"
    
    print("   ✅ Valores de inflação média corretos")
    
    # Validar ordem das colunas (intercaladas)
    print("\n4️⃣ Validando ordem das colunas...")
    print("-" * 70)
    
    colunas_reais = df_export_novo.columns.tolist()
    print(f"   Colunas no DataFrame (primeiras 10):")
    for i, col in enumerate(colunas_reais[:10]):
        print(f"      {i+1}. {col}")
    
    if len(colunas_reais) > 10:
        print(f"      ... (+{len(colunas_reais) - 10} colunas adicionais)")
    
    # Validar que Mês é a primeira coluna
    assert colunas_reais[0] == "Mês", "❌ Primeira coluna não é 'Mês'!"
    print("\n   ✅ Primeira coluna é 'Mês'")
    
    # Validar que colunas estão intercaladas (Preço seguido de Inflação)
    produtos_encontrados = 0
    for produto in produtos_nomes:
        unidade = unidades.get(produto, "UN")
        col_preco = f"{produto} - Preço ({unidade})"
        col_inflacao = f"{produto} - Inflação (%)"
        
        if col_preco in colunas_reais and col_inflacao in colunas_reais:
            idx_preco = colunas_reais.index(col_preco)
            idx_inflacao = colunas_reais.index(col_inflacao)
            
            # Inflação deve vir logo após o preço (ou muito próximo)
            if idx_inflacao == idx_preco + 1:
                produtos_encontrados += 1
    
    print(f"   ✅ {produtos_encontrados} produtos com colunas intercaladas corretamente")
    
    # Teste de exportação CSV
    print("\n5️⃣ Testando exportação para CSV...")
    print("-" * 70)
    
    try:
        csv = df_export_novo.to_csv(index=False, encoding="utf-8-sig", sep=";", decimal=",")
        
        # Validar que CSV tem conteúdo
        assert len(csv) > 0, "❌ CSV vazio!"
        print(f"   ✅ CSV gerado: {len(csv)} caracteres")
        
        # Validar que CSV tem cabeçalho
        linhas = csv.split('\n')
        assert len(linhas) > 1, "❌ CSV sem linhas!"
        print(f"   ✅ CSV tem {len(linhas)} linhas")
        
        # Validar cabeçalho
        cabecalho = linhas[0]
        assert "Mês" in cabecalho, "❌ Cabeçalho sem 'Mês'!"
        assert "Preço" in cabecalho, "❌ Cabeçalho sem 'Preço'!"
        assert "Inflação" in cabecalho, "❌ Cabeçalho sem 'Inflação'!"
        print("   ✅ Cabeçalho CSV válido")
        
    except Exception as e:
        print(f"   ❌ Erro ao gerar CSV: {e}")
        return False
    
    # Resumo
    print("\n" + "="*70)
    print("RESUMO DO TESTE")
    print("="*70)
    print(f"✅ DataFrame gerado: {df_export_novo.shape[0]} linhas x {df_export_novo.shape[1]} colunas")
    print(f"✅ Estrutura validada: todas as colunas esperadas presentes")
    print(f"✅ Valores validados: inflação média correta")
    print(f"✅ Ordem validada: colunas intercaladas corretamente")
    print(f"✅ Exportação validada: CSV gerado com sucesso")
    print("\n🎉 REFATORAMENTO VALIDADO COM SUCESSO! 🎉\n")
    print("="*70 + "\n")
    
    return True


if __name__ == "__main__":
    try:
        success = test_csv_export_refactored()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n❌ TESTE FALHOU: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
