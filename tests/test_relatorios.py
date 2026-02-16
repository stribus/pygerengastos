"""Testes para funções de relatórios com fixtures determinísticas."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.database import (
    conexao,
    inicializar_banco,
    obter_top_produtos_por_quantidade,
    obter_custos_unitarios_mensais,
    obter_unidades_produtos,
    salvar_nota,
    seed_categorias_csv,
)
from src.scrapers.receita_rs import NotaFiscal, NotaItem, Pagamento


def _criar_nota_teste(
    chave: str,
    emissao_data: str,
    itens: list[tuple[str, Decimal, Decimal, str]],
) -> NotaFiscal:
    """Cria uma nota fiscal de teste com itens customizados.
    
    Args:
        chave: Chave de acesso da nota
        emissao_data: Data de emissão no formato ISO (YYYY-MM-DD)
        itens: Lista de tuplas (descricao, valor_unitario, quantidade, unidade)
    """
    nota_itens = [
        NotaItem(
            descricao=desc,
            codigo=None,
            valor_unitario=val_unit,
            quantidade=qtd,
            valor_total=val_unit * qtd,
            unidade=unid,
        )
        for desc, val_unit, qtd, unid in itens
    ]
    
    valor_total = sum(item.valor_total for item in nota_itens)
    
    # Convert YYYY-MM-DD to DD/MM/YYYY format expected by database
    data_obj = datetime.fromisoformat(emissao_data)
    emissao_texto = data_obj.strftime("%d/%m/%Y 10:00:00")
    
    return NotaFiscal(
        chave_acesso=chave,
        emitente_nome="Mercado Teste Ltda",
        emitente_cnpj="12.345.678/0001-90",
        emitente_endereco="Rua Teste, 123",
        numero="12345",
        serie="1",
        emissao=emissao_texto,
        total_itens=len(nota_itens),
        valor_total=valor_total,
        valor_pago=valor_total,
        tributos=Decimal("0"),
        itens=nota_itens,
        pagamentos=[
            Pagamento(forma="Dinheiro", valor=valor_total)
        ],
    )


@pytest.fixture
def db_com_dados_teste(tmp_path):
    """Cria banco temporário com dados de teste para relatórios."""
    db_path = tmp_path / "test_relatorios.db"
    
    # Inicializar banco e seed de categorias
    inicializar_banco(db_path=db_path)
    csv_path = tmp_path / "categorias.csv"
    csv_path.write_text(
        "Grupo,Categoria\n"
        "Alimentação,Alimentos\n"
        "Limpeza,Produtos de Limpeza\n",
        encoding="utf-8"
    )
    seed_categorias_csv(csv_path, db_path=db_path)
    
    # Criar 3 notas com produtos repetidos em meses diferentes
    base_date = datetime(2025, 1, 15)
    
    # Nota 1: Janeiro 2025
    nota1 = _criar_nota_teste(
        "11111111111111111111111111111111111111111111",
        base_date.date().isoformat(),
        [
            ("ARROZ BRANCO 5KG", Decimal("25.00"), Decimal("2"), "UN"),
            ("FEIJAO PRETO 1KG", Decimal("8.00"), Decimal("3"), "UN"),
            ("DETERGENTE NEUTRO 500ML", Decimal("2.50"), Decimal("5"), "UN"),
        ],
    )
    
    # Nota 2: Fevereiro 2025 (preços diferentes)
    nota2 = _criar_nota_teste(
        "22222222222222222222222222222222222222222222",
        (base_date + timedelta(days=31)).date().isoformat(),
        [
            ("ARROZ BRANCO 5KG", Decimal("27.00"), Decimal("1"), "UN"),
            ("FEIJAO PRETO 1KG", Decimal("8.50"), Decimal("2"), "UN"),
            ("SABAO EM PO 1KG", Decimal("15.00"), Decimal("1"), "UN"),
        ],
    )
    
    # Nota 3: Março 2025
    nota3 = _criar_nota_teste(
        "33333333333333333333333333333333333333333333",
        (base_date + timedelta(days=62)).date().isoformat(),
        [
            ("ARROZ BRANCO 5KG", Decimal("26.00"), Decimal("2"), "UN"),
            ("DETERGENTE NEUTRO 500ML", Decimal("2.80"), Decimal("3"), "UN"),
        ],
    )
    
    # Salvar notas no banco
    for nota in [nota1, nota2, nota3]:
        salvar_nota(nota, db_path=db_path)
    
    return db_path


def test_obter_top_produtos_por_quantidade(db_com_dados_teste):
    """Testa ranking de produtos por quantidade total comprada."""
    db_path = db_com_dados_teste
    
    top_produtos = obter_top_produtos_por_quantidade(
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        top_n=10,
        db_path=db_path,
    )
    
    # Deve retornar todos os produtos ordenados por quantidade
    assert len(top_produtos) == 4
    
    # Verificar se está ordenado (maior quantidade primeiro)
    quantidades = [p["quantidade_total"] for p in top_produtos]
    assert quantidades == sorted(quantidades, reverse=True)
    
    # Primeiro produto deve ser Detergente (5+3=8 unidades)
    assert top_produtos[0]["produto_nome"] == "Detergente Neutro"
    assert top_produtos[0]["quantidade_total"] == 8.0
    
    # Produtos 2 e 3: Arroz (2+1+2=5) e Feijao (3+2=5) - ordem pode variar
    produtos_5_unidades = {top_produtos[1]["produto_nome"], top_produtos[2]["produto_nome"]}
    assert produtos_5_unidades == {"Arroz Branco", "Feijao Preto"}
    assert top_produtos[1]["quantidade_total"] == 5.0
    assert top_produtos[2]["quantidade_total"] == 5.0


def test_obter_top_produtos_com_filtro_data(db_com_dados_teste):
    """Testa filtro de período no ranking de produtos."""
    db_path = db_com_dados_teste
    
    # Apenas Janeiro
    top_jan = obter_top_produtos_por_quantidade(
        data_inicio="2025-01-01",
        data_fim="2025-01-31",
        top_n=10,
        db_path=db_path,
    )
    
    # Apenas 3 produtos em janeiro
    assert len(top_jan) == 3
    assert top_jan[0]["produto_nome"] == "Detergente Neutro"
    assert top_jan[0]["quantidade_total"] == 5.0


def test_obter_top_produtos_com_limit(db_com_dados_teste):
    """Testa limite de resultados no ranking."""
    db_path = db_com_dados_teste
    
    top_2 = obter_top_produtos_por_quantidade(
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        top_n=2,
        db_path=db_path,
    )
    
    assert len(top_2) == 2


def test_obter_custos_unitarios_mensais(db_com_dados_teste):
    """Testa cálculo de custos unitários médios mensais."""
    db_path = db_com_dados_teste
    
    # Usar nomes normalizados (sem acentos) como retornado pelo banco
    produtos = ["Arroz Branco", "Feijao Preto"]
    custos = obter_custos_unitarios_mensais(
        produtos,
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        db_path=db_path,
    )
    
    # Deve ter registros para ambos os produtos
    assert len(custos) > 0
    
    # Separar por produto
    custos_arroz = [c for c in custos if c["produto_nome"] == "Arroz Branco"]
    custos_feijao = [c for c in custos if c["produto_nome"] == "Feijao Preto"]
    
    # Arroz aparece em 3 meses
    assert len(custos_arroz) == 3
    
    # Feijao aparece em 2 meses
    assert len(custos_feijao) == 2
    
    # Verificar estrutura dos registros
    primeiro_custo = custos[0]
    assert "produto_nome" in primeiro_custo
    assert "ano_mes" in primeiro_custo
    assert "custo_unitario_medio" in primeiro_custo
    
    # Verificar formato ano_mes (YYYY-MM)
    assert len(primeiro_custo["ano_mes"]) == 7
    assert primeiro_custo["ano_mes"].count("-") == 1


def test_obter_custos_unitarios_lista_vazia(db_com_dados_teste):
    """Testa comportamento com lista vazia de produtos."""
    db_path = db_com_dados_teste
    
    custos = obter_custos_unitarios_mensais(
        [],
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        db_path=db_path,
    )
    
    assert custos == []


def test_obter_custos_unitarios_calcula_media_ponderada(db_com_dados_teste):
    """Testa se o custo médio é calculado corretamente (ponderado por quantidade)."""
    db_path = db_com_dados_teste
    
    # Arroz em Janeiro: 2 unidades a 25.00 = custo unitário de 25.00
    custos_arroz_jan = obter_custos_unitarios_mensais(
        ["Arroz Branco"],
        data_inicio="2025-01-01",
        data_fim="2025-01-31",
        db_path=db_path,
    )
    
    assert len(custos_arroz_jan) == 1
    assert custos_arroz_jan[0]["ano_mes"] == "2025-01"
    assert abs(custos_arroz_jan[0]["custo_unitario_medio"] - 25.00) < 0.01


def test_obter_unidades_produtos(db_com_dados_teste):
    """Testa mapeamento de produtos para unidades mais comuns."""
    db_path = db_com_dados_teste
    
    # Usar nomes normalizados (sem acentos)
    produtos = ["Arroz Branco", "Feijao Preto", "Detergente Neutro"]
    unidades = obter_unidades_produtos(produtos, db_path=db_path)
    
    # Deve retornar unidade para cada produto
    assert len(unidades) == 3
    
    # Todos os produtos de teste usam "UN"
    assert unidades["Arroz Branco"] == "UN"
    assert unidades["Feijao Preto"] == "UN"
    assert unidades["Detergente Neutro"] == "UN"


def test_obter_unidades_produtos_lista_vazia(db_com_dados_teste):
    """Testa comportamento com lista vazia de produtos."""
    db_path = db_com_dados_teste
    
    unidades = obter_unidades_produtos([], db_path=db_path)
    
    assert unidades == {}


def test_obter_unidades_produtos_inexistentes(db_com_dados_teste):
    """Testa comportamento com produtos que não existem no banco."""
    db_path = db_com_dados_teste
    
    unidades = obter_unidades_produtos(
        ["Produto Inexistente", "Outro Inexistente"],
        db_path=db_path,
    )
    
    assert unidades == {}


def test_calculos_matematicos_basicos():
    """Testa cálculos auxiliares para relatórios (variação e inflação)."""
    
    # Teste de variação percentual
    def calc_var(v_ant, v_atu):
        if v_ant == 0:
            return 0.0
        return ((v_atu - v_ant) / v_ant) * 100
    
    var = calc_var(100.0, 110.0)
    assert abs(var - 10.0) < 0.01
    
    var_neg = calc_var(100.0, 90.0)
    assert abs(var_neg - (-10.0)) < 0.01
    
    var_zero = calc_var(0.0, 100.0)
    assert var_zero == 0.0
    
    # Teste de inflação acumulada
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
    
    # Esperado: [0%, 10%, 21%]
    assert abs(inflacao[0] - 0.0) < 0.01
    assert abs(inflacao[1] - 10.0) < 0.01
    assert abs(inflacao[2] - 21.0) < 0.01
    
    # Teste com valores constantes
    valores_const = [100.0, 100.0, 100.0]
    inflacao_const = calc_inflacao(valores_const)
    assert all(abs(i) < 0.01 for i in inflacao_const)
