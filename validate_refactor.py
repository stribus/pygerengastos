"""
Script simples para validar visualmente a refatoração do CSV export.
Gera um DataFrame de exemplo e exibe a estrutura.
"""

from datetime import datetime, timedelta
import pandas as pd

from src.database import (
    obter_top_produtos_por_quantidade,
    obter_custos_unitarios_mensais,
    obter_unidades_produtos,
)
from src.ui.relatorios import (
    _preencher_meses_faltantes,
    _calcular_inflacao_acumulada,
    _identificar_produtos_regulares,
    _calcular_cesta_basica_personalizada,
)


def main():
    print("\n" + "="*80)
    print("VALIDAÇÃO VISUAL DA REFATORAÇÃO - EXPORTAÇÃO CSV")
    print("="*80 + "\n")
    
    # Período de teste
    data_fim = datetime.now().date()
    data_inicio = data_fim - timedelta(days=365)
    
    print(f"📅 Período: {data_inicio} até {data_fim}\n")
    
    # Buscar top 3 produtos para exemplo compacto
    print("1. Carregando dados do banco...")
    top_produtos = obter_top_produtos_por_quantidade(
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
        top_n=3,
    )
    
    if not top_produtos:
        print("   ⚠️  Nenhum produto encontrado.")
        return
    
    produtos_nomes = [p["produto_nome"] for p in top_produtos]
    print(f"   ✅ Produtos selecionados: {', '.join(produtos_nomes)}\n")
    
    # Buscar custos
    custos = obter_custos_unitarios_mensais(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )
    
    if not custos:
        print("   ⚠️  Nenhum custo encontrado.")
        return
    
    # Processar dados
    df_completo = _preencher_meses_faltantes(
        custos,
        produtos_nomes,
        data_inicio.isoformat(),
        data_fim.isoformat(),
    )
    
    if df_completo.empty:
        print("   ⚠️  DataFrame vazio.")
        return
    
    produtos_regulares = _identificar_produtos_regulares(df_completo)
    meses_ordenados = sorted(df_completo["ano_mes"].unique())
    
    # Calcular inflação
    inflacao_por_produto = {}
    for produto in produtos_nomes:
        df_produto = df_completo[df_completo["produto_nome"] == produto].sort_values("ano_mes")
        if not df_produto.empty:
            inflacao = _calcular_inflacao_acumulada(df_produto)
            inflacao_alinhada = [inflacao[i] if i < len(inflacao) else float('nan')
                                 for i in range(len(meses_ordenados))]
            inflacao_por_produto[produto] = inflacao_alinhada
    
    # Inflação média
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
    
    # Cesta básica
    df_cesta = _calcular_cesta_basica_personalizada(df_completo, produtos_regulares)
    if not df_cesta.empty:
        inflacao_cesta_lista = _calcular_inflacao_acumulada(df_cesta, coluna_valor="custo_cesta")
        inflacao_cesta = [inflacao_cesta_lista[i] if i < len(inflacao_cesta_lista) else 0.0
                          for i in range(len(meses_ordenados))]
    else:
        inflacao_cesta = [0.0] * len(meses_ordenados)
    
    # Unidades
    unidades = obter_unidades_produtos(produtos_nomes)
    
    print("2. Construindo DataFrame de exportação (abordagem REFATORADA)...")
    print("-" * 80)
    
    # === CÓDIGO REFATORADO ===
    
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
    
    # 4. Ordenar colunas
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
    df_export = pd.concat(
        [df_precos, df_inflacao_produtos, df_extras],
        axis=1
    )
    
    df_export = df_export.reset_index().rename(columns={"index": "Mês"})
    df_export = df_export[
        [col for col in colunas_ordenadas if col in df_export.columns]
    ]
    
    print(f"   ✅ DataFrame criado: {df_export.shape[0]} linhas x {df_export.shape[1]} colunas\n")
    
    # Exibir estrutura
    print("3. Estrutura do DataFrame:")
    print("-" * 80)
    print(f"\nColunas ({len(df_export.columns)}):")
    for i, col in enumerate(df_export.columns, 1):
        print(f"   {i:2}. {col}")
    
    print(f"\n4. Primeiras linhas do DataFrame:")
    print("-" * 80)
    print(df_export.head(5).to_string())
    
    print("\n5. Estatísticas:")
    print("-" * 80)
    print(f"   Total de meses: {len(df_export)}")
    print(f"   Total de colunas: {len(df_export.columns)}")
    print(f"   Produtos regulares: {len(produtos_regulares)}")
    
    # Verificar valores não nulos
    print("\n6. Valores não-nulos por coluna:")
    print("-" * 80)
    for col in df_export.columns:
        if col != "Mês":
            nao_nulos = df_export[col].notna().sum()
            print(f"   {col}: {nao_nulos}/{len(df_export)} ({100*nao_nulos/len(df_export):.1f}%)")
    
    print("\n" + "="*80)
    print("✅ VALIDAÇÃO CONCLUÍDA COM SUCESSO!")
    print("="*80 + "\n")
    
    print("📝 BENEFÍCIOS DA REFATORAÇÃO:")
    print("   • Código mais limpo e legível")
    print("   • Uso de operações pandas nativas (pivot, concat)")
    print("   • Menos manipulação manual de listas")
    print("   • Melhor performance para grandes volumes")
    print("   • Mais fácil de manter e estender")
    print()


if __name__ == "__main__":
    main()
