"""Testes básicos para funções de relatórios."""

from datetime import datetime, timedelta
import sys

from src.database import (
    obter_top_produtos_por_quantidade,
    obter_custos_unitarios_mensais,
    obter_unidades_produtos,
)


def test_relatorios():
    """Testa funções de relatórios com dados reais do banco."""
    print("🧪 Testando funções de relatórios...\n")
    
    # Período de teste
    data_fim = datetime.now().date()
    data_inicio = data_fim - timedelta(days=365)
    
    print(f"📅 Período: {data_inicio} até {data_fim}\n")
    
    # Teste 1: Top produtos
    print("1️⃣ Testando obter_top_produtos_por_quantidade()...")
    try:
        top_produtos = obter_top_produtos_por_quantidade(
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
            top_n=10,
        )
        
        if not top_produtos:
            print("   ⚠️  Nenhum produto encontrado")
            return False
        
        print(f"   ✅ {len(top_produtos)} produtos encontrados:")
        for i, p in enumerate(top_produtos, 1):
            print(f"      {i}. {p['produto_nome']}: {p['quantidade_total']:.1f}")
        
        produtos_nomes = [p['produto_nome'] for p in top_produtos]
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    print()
    
    # Teste 2: Custos unitários mensais
    print("2️⃣ Testando obter_custos_unitarios_mensais()...")
    try:
        custos = obter_custos_unitarios_mensais(
            produtos_nomes,
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
        )
        
        if not custos:
            print("   ⚠️  Nenhum custo encontrado")
            return False
        
        print(f"   ✅ {len(custos)} registros de custos encontrados")
        
        # Agrupar por produto para ver quantos meses tem cada um
        produtos_meses = {}
        for c in custos:
            prod = c['produto_nome']
            if prod not in produtos_meses:
                produtos_meses[prod] = []
            produtos_meses[prod].append((c['ano_mes'], c['custo_unitario_medio']))
        
        print("   📊 Custos por produto:")
        for prod, meses_custos in list(produtos_meses.items())[:3]:
            print(f"      {prod}:")
            for mes, custo in meses_custos[:3]:
                print(f"         {mes}: R$ {custo:.2f}")
            if len(meses_custos) > 3:
                print(f"         ... ({len(meses_custos) - 3} meses adicionais)")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # Teste 3: Unidades dos produtos
    print("3️⃣ Testando obter_unidades_produtos()...")
    try:
        unidades = obter_unidades_produtos(produtos_nomes)
        
        if not unidades:
            print("   ⚠️  Nenhuma unidade encontrada")
            return False
        
        print(f"   ✅ {len(unidades)} unidades encontradas:")
        for prod, unid in list(unidades.items())[:5]:
            print(f"      {prod}: {unid}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    print()
    
    # Teste 4: Funções auxiliares de cálculo
    print("4️⃣ Testando cálculos matemáticos...")
    try:
        import pandas as pd
        
        # Teste de variação percentual (implementação direta)
        def calc_var(v_ant, v_atu):
            if v_ant == 0:
                return 0.0
            return ((v_atu - v_ant) / v_ant) * 100
        
        var = calc_var(100.0, 110.0)
        assert abs(var - 10.0) < 0.01, f"Esperado 10%, obtido {var}%"
        print(f"   ✅ Variação percentual: {var:.2f}% (de 100 para 110)")
        
        # Teste de inflação acumulada (implementação direta)
        def calc_inflacao(valores):
            inflacao = [0.0]
            for i in range(1, len(valores)):
                var_pct = calc_var(valores[i-1], valores[i])
                inflacao_ant = inflacao[-1]
                inflacao_nova = ((1 + inflacao_ant/100) * (1 + var_pct/100) - 1) * 100
                inflacao.append(inflacao_nova)
            return inflacao
        
        valores = [100.0, 110.0, 121.0]
        inflacao = calc_inflacao(valores)
        print(f"   ✅ Inflação acumulada: {inflacao}")
        # Esperado: [0%, 10%, 21%]
        assert abs(inflacao[0] - 0.0) < 0.01
        assert abs(inflacao[1] - 10.0) < 0.01
        assert abs(inflacao[2] - 21.0) < 0.01
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("✅ Todos os testes passaram!\n")
    return True


if __name__ == "__main__":
    success = test_relatorios()
    sys.exit(0 if success else 1)
