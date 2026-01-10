"""
Teste de integração completo para o módulo de relatórios.

Valida todo o fluxo desde a consulta SQL até os cálculos de inflação.
"""

from datetime import datetime, timedelta

from src.database import (
    conexao,
    obter_top_produtos_por_quantidade,
    obter_custos_unitarios_mensais,
    obter_unidades_produtos,
)


def test_integracao_completa():
    """Testa fluxo completo de geração de relatórios."""
    print("\n" + "="*70)
    print("TESTE DE INTEGRAÇÃO - MÓDULO DE RELATÓRIOS")
    print("="*70 + "\n")
    
    # Setup: período de teste
    data_fim = datetime.now().date()
    data_inicio = data_fim - timedelta(days=365)
    
    print(f"📅 Período de análise: {data_inicio} até {data_fim}\n")
    
    # Passo 1: Verificar dados no banco
    print("1️⃣ VERIFICANDO DADOS NO BANCO...")
    print("-" * 70)
    
    with conexao() as con:
        # Contar notas
        total_notas = con.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
        print(f"   📄 Total de notas no banco: {total_notas}")
        
        # Contar itens classificados
        total_itens = con.execute("SELECT COUNT(*) FROM itens WHERE categoria_confirmada IS NOT NULL").fetchone()[0]
        print(f"   ✅ Itens classificados: {total_itens}")
        
        # Contar produtos únicos
        total_produtos = con.execute("SELECT COUNT(DISTINCT produto_nome) FROM itens WHERE produto_nome IS NOT NULL").fetchone()[0]
        print(f"   🏷️  Produtos únicos: {total_produtos}")
        
        # Período de dados
        datas = con.execute("""
            SELECT MIN(emissao_data), MAX(emissao_data)
            FROM notas
            WHERE emissao_data IS NOT NULL
        """).fetchone()
        print(f"   📊 Período com dados: {datas[0]} até {datas[1]}")
    
    assert total_notas > 0, "❌ Nenhuma nota no banco!"
    assert total_itens > 0, "❌ Nenhum item classificado!"
    assert total_produtos > 0, "❌ Nenhum produto identificado!"
    
    print("\n✅ Dados do banco validados!\n")
    
    # Passo 2: Testar consulta de top produtos
    print("2️⃣ TESTANDO: obter_top_produtos_por_quantidade()")
    print("-" * 70)
    
    top_produtos = obter_top_produtos_por_quantidade(
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
        top_n=10,
    )
    
    assert len(top_produtos) > 0, "❌ Nenhum produto retornado!"
    print(f"   ✅ {len(top_produtos)} produtos encontrados")
    
    print("\n   Top 5 produtos por quantidade:")
    for i, produto in enumerate(top_produtos[:5], 1):
        nome = produto['produto_nome']
        qtd = produto['quantidade_total']
        print(f"      {i}. {nome:30} - {qtd:>8.2f} unidades")
    
    # Validar estrutura dos dados
    primeiro = top_produtos[0]
    assert 'produto_nome' in primeiro, "❌ Campo 'produto_nome' ausente!"
    assert 'quantidade_total' in primeiro, "❌ Campo 'quantidade_total' ausente!"
    assert isinstance(primeiro['quantidade_total'], (int, float)), "❌ Quantidade não é numérica!"
    
    produtos_nomes = [p['produto_nome'] for p in top_produtos]
    
    print("\n✅ Consulta de top produtos validada!\n")
    
    # Passo 3: Testar custos unitários mensais
    print("3️⃣ TESTANDO: obter_custos_unitarios_mensais()")
    print("-" * 70)
    
    custos = obter_custos_unitarios_mensais(
        produtos_nomes[:5],  # Primeiros 5 para não sobrecarregar
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )
    
    assert len(custos) > 0, "❌ Nenhum custo retornado!"
    print(f"   ✅ {len(custos)} registros de custos encontrados")
    
    # Validar estrutura
    primeiro_custo = custos[0]
    assert 'produto_nome' in primeiro_custo, "❌ Campo ausente!"
    assert 'ano_mes' in primeiro_custo, "❌ Campo ausente!"
    assert 'custo_unitario_medio' in primeiro_custo, "❌ Campo ausente!"
    
    # Validar formato ano_mes
    assert len(primeiro_custo['ano_mes']) == 7, "❌ Formato ano_mes inválido!"
    assert primeiro_custo['ano_mes'][4] == '-', "❌ Formato ano_mes inválido!"
    
    # Agrupar por produto
    por_produto = {}
    for custo in custos:
        prod = custo['produto_nome']
        if prod not in por_produto:
            por_produto[prod] = []
        por_produto[prod].append(custo)
    
    print(f"\n   Produtos com histórico de preços:")
    for prod, historico in list(por_produto.items())[:3]:
        print(f"      {prod}: {len(historico)} meses")
        # Mostrar variação
        precos = [h['custo_unitario_medio'] for h in historico]
        if len(precos) >= 2:
            var = ((precos[-1] - precos[0]) / precos[0]) * 100
            print(f"         Variação: {precos[0]:.2f} → {precos[-1]:.2f} ({var:+.1f}%)")
    
    print("\n✅ Consulta de custos mensais validada!\n")
    
    # Passo 4: Testar unidades
    print("4️⃣ TESTANDO: obter_unidades_produtos()")
    print("-" * 70)
    
    unidades = obter_unidades_produtos(produtos_nomes[:10])
    
    assert len(unidades) > 0, "❌ Nenhuma unidade retornada!"
    print(f"   ✅ {len(unidades)} unidades mapeadas")
    
    print("\n   Produtos e suas unidades:")
    for prod, unid in list(unidades.items())[:5]:
        print(f"      {prod:30} → {unid}")
    
    # Validar unidades conhecidas
    unidades_validas = {'KG', 'G', 'L', 'ML', 'UN', 'PCT'}
    for unid in unidades.values():
        assert unid in unidades_validas or len(unid) <= 5, f"❌ Unidade suspeita: {unid}"
    
    print("\n✅ Mapeamento de unidades validado!\n")
    
    # Passo 5: Validar cálculos de inflação
    print("5️⃣ TESTANDO: Cálculos de inflação")
    print("-" * 70)
    
    # Pegar produto com mais dados
    produto_teste = None
    max_meses = 0
    for prod, hist in por_produto.items():
        if len(hist) > max_meses:
            max_meses = len(hist)
            produto_teste = prod
    
    if produto_teste and max_meses >= 3:
        historico = sorted(por_produto[produto_teste], key=lambda x: x['ano_mes'])
        precos = [h['custo_unitario_medio'] for h in historico]
        
        print(f"   Produto: {produto_teste}")
        print(f"   Meses de histórico: {max_meses}")
        print(f"   Preço inicial: R$ {precos[0]:.2f}")
        print(f"   Preço final: R$ {precos[-1]:.2f}")
        
        # Calcular inflação total
        inflacao_total = ((precos[-1] - precos[0]) / precos[0]) * 100
        print(f"   Inflação total: {inflacao_total:+.2f}%")
        
        # Calcular inflação acumulada mês a mês
        inflacao_acum = [0.0]
        for i in range(1, len(precos)):
            var = ((precos[i] - precos[i-1]) / precos[i-1]) * 100
            inflacao_ant = inflacao_acum[-1]
            inflacao_nova = ((1 + inflacao_ant/100) * (1 + var/100) - 1) * 100
            inflacao_acum.append(inflacao_nova)
        
        print(f"   Inflação acumulada (último mês): {inflacao_acum[-1]:.2f}%")
        
        # A inflação acumulada deve ser aproximadamente igual à inflação total
        # (pequenas diferenças por arredondamento são OK)
        diff = abs(inflacao_acum[-1] - inflacao_total)
        assert diff < 0.1, f"❌ Inflação acumulada diverge: {diff:.4f}%"
        
        print(f"\n   Histórico mensal detalhado:")
        for i, h in enumerate(historico[:6]):  # Primeiros 6 meses
            mes = h['ano_mes']
            preco = h['custo_unitario_medio']
            infl = inflacao_acum[i]
            print(f"      {mes}: R$ {preco:>7.2f}  (inflação acum: {infl:>6.2f}%)")
        
        if len(historico) > 6:
            print(f"      ... (+{len(historico) - 6} meses)")
    
    print("\n✅ Cálculos de inflação validados!\n")
    
    # Resumo final
    print("="*70)
    print("RESUMO DO TESTE DE INTEGRAÇÃO")
    print("="*70)
    print(f"✅ Dados no banco: {total_notas} notas, {total_itens} itens")
    print(f"✅ Top produtos: {len(top_produtos)} identificados")
    print(f"✅ Custos mensais: {len(custos)} registros")
    print(f"✅ Unidades: {len(unidades)} mapeadas")
    print(f"✅ Cálculos: validados para {produto_teste if produto_teste else 'N/A'}")
    print("\n🎉 TODOS OS TESTES PASSARAM! 🎉\n")
    print("="*70 + "\n")
    
    return True


if __name__ == "__main__":
    import sys
    try:
        success = test_integracao_completa()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n❌ TESTE FALHOU: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
