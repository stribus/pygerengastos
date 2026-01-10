"""Script para popular banco de dados com dados de teste para demonstração."""

from datetime import datetime, timedelta
from decimal import Decimal
import random

from src.database import salvar_nota, registrar_classificacao_itens, seed_categorias_csv
from src.scrapers.receita_rs import NotaFiscal, NotaItem, Pagamento


def criar_nota_teste(
    chave_base: str,
    data_emissao: datetime,
    estabelecimento: str,
    itens: list[tuple[str, str, Decimal, Decimal]],  # (descricao, unidade, quantidade, preco_unitario)
) -> NotaFiscal:
    """Cria uma nota fiscal de teste."""
    chave = f"43{data_emissao.strftime('%y%m')}{chave_base}"
    
    nota_itens = []
    valor_total = Decimal("0")
    
    for idx, (desc, unidade, qtd, preco_unit) in enumerate(itens, 1):
        valor_item = qtd * preco_unit
        valor_total += valor_item
        
        nota_itens.append(NotaItem(
            descricao=desc,
            codigo=f"COD{idx:03d}",
            quantidade=qtd,
            unidade=unidade,
            valor_unitario=preco_unit,
            valor_total=valor_item,
        ))
    
    return NotaFiscal(
        chave_acesso=chave,
        emitente_nome=estabelecimento,
        emitente_cnpj=f"12345678000{random.randint(100, 999):03d}",
        emitente_endereco=f"Rua Teste, {random.randint(1, 999)}",
        numero=f"{random.randint(1000, 9999)}",
        serie="1",
        emissao=data_emissao.strftime("%d/%m/%Y %H:%M:%S"),
        itens=nota_itens,
        total_itens=len(nota_itens),
        valor_total=valor_total,
        valor_pago=valor_total,
        tributos=Decimal("0"),
        consumidor_cpf="12345678900",
        consumidor_nome="João Silva",
        pagamentos=[Pagamento(forma="Dinheiro", valor=valor_total)],
    )


def popular_dados_teste():
    """Popula o banco com dados de teste para demonstração."""
    print("Inicializando banco e categorias...")
    seed_categorias_csv()
    
    # Produtos de teste com variação de preços ao longo do tempo
    produtos_base = [
        ("Arroz Branco", "KG", Decimal("5.0"), [
            Decimal("4.50"), Decimal("4.80"), Decimal("5.20"), Decimal("5.50"),
            Decimal("5.80"), Decimal("6.00"), Decimal("6.20"), Decimal("6.50"),
            Decimal("6.80"), Decimal("7.00"), Decimal("7.20"), Decimal("7.50")
        ]),
        ("Feijão Preto", "KG", Decimal("1.0"), [
            Decimal("7.00"), Decimal("7.20"), Decimal("7.50"), Decimal("7.80"),
            Decimal("8.00"), Decimal("8.20"), Decimal("8.50"), Decimal("8.80"),
            Decimal("9.00"), Decimal("9.20"), Decimal("9.50"), Decimal("9.80")
        ]),
        ("Óleo De Soja", "UN", Decimal("2.0"), [
            Decimal("6.50"), Decimal("6.70"), Decimal("7.00"), Decimal("7.30"),
            Decimal("7.50"), Decimal("7.80"), Decimal("8.00"), Decimal("8.30"),
            Decimal("8.50"), Decimal("8.80"), Decimal("9.00"), Decimal("9.20")
        ]),
        ("Açúcar Cristal", "KG", Decimal("2.0"), [
            Decimal("3.50"), Decimal("3.60"), Decimal("3.80"), Decimal("4.00"),
            Decimal("4.20"), Decimal("4.40"), Decimal("4.60"), Decimal("4.80"),
            Decimal("5.00"), Decimal("5.20"), Decimal("5.40"), Decimal("5.60")
        ]),
        ("Café Torrado", "UN", Decimal("1.0"), [
            Decimal("12.00"), Decimal("12.50"), Decimal("13.00"), Decimal("13.50"),
            Decimal("14.00"), Decimal("14.50"), Decimal("15.00"), Decimal("15.50"),
            Decimal("16.00"), Decimal("16.50"), Decimal("17.00"), Decimal("17.50")
        ]),
        ("Leite Integral", "UN", Decimal("4.0"), [
            Decimal("4.50"), Decimal("4.60"), Decimal("4.80"), Decimal("5.00"),
            Decimal("5.20"), Decimal("5.40"), Decimal("5.60"), Decimal("5.80"),
            Decimal("6.00"), Decimal("6.20"), Decimal("6.40"), Decimal("6.60")
        ]),
        ("Macarrão Espaguete", "UN", Decimal("2.0"), [
            Decimal("3.50"), Decimal("3.60"), Decimal("3.80"), Decimal("4.00"),
            Decimal("4.20"), Decimal("4.40"), Decimal("4.60"), Decimal("4.80"),
            Decimal("5.00"), Decimal("5.20"), Decimal("5.40"), Decimal("5.60")
        ]),
        ("Carne Moída", "KG", Decimal("1.5"), [
            Decimal("22.00"), Decimal("23.00"), Decimal("24.00"), Decimal("25.00"),
            Decimal("26.00"), Decimal("27.00"), Decimal("28.00"), Decimal("29.00"),
            Decimal("30.00"), Decimal("31.00"), Decimal("32.00"), Decimal("33.00")
        ]),
        ("Frango Congelado", "KG", Decimal("2.0"), [
            Decimal("10.00"), Decimal("10.50"), Decimal("11.00"), Decimal("11.50"),
            Decimal("12.00"), Decimal("12.50"), Decimal("13.00"), Decimal("13.50"),
            Decimal("14.00"), Decimal("14.50"), Decimal("15.00"), Decimal("15.50")
        ]),
        ("Tomate", "KG", Decimal("1.0"), [
            Decimal("5.00"), Decimal("5.50"), Decimal("6.00"), Decimal("6.50"),
            Decimal("7.00"), Decimal("6.50"), Decimal("6.00"), Decimal("5.50"),
            Decimal("5.00"), Decimal("5.50"), Decimal("6.00"), Decimal("6.50")
        ]),
    ]
    
    # Produtos esporádicos (para testar filtro de regularidade)
    produtos_esporadicos = [
        ("Chocolate Especial", "UN", Decimal("1.0"), [
            None, None, Decimal("15.00"), None, None, Decimal("16.00"),
            None, None, None, Decimal("17.00"), None, None
        ]),
        ("Vinho Tinto", "UN", Decimal("1.0"), [
            Decimal("35.00"), None, None, None, Decimal("38.00"), None,
            None, None, None, None, Decimal("40.00"), None
        ]),
    ]
    
    # Criar notas para os últimos 12 meses
    data_base = datetime.now()
    estabelecimentos = ["Supermercado ABC", "Mercado XYZ", "Loja do João"]
    
    print("Criando notas fiscais de teste...")
    
    for mes_offset in range(11, -1, -1):  # Últimos 12 meses
        data_mes = data_base - timedelta(days=30 * mes_offset)
        data_mes = data_mes.replace(day=15)  # Sempre dia 15 do mês
        
        # Criar 2-3 notas por mês
        for nota_idx in range(random.randint(2, 3)):
            itens_nota = []
            
            # Adicionar produtos regulares
            for prod_idx, (nome, unidade, qtd_base, precos) in enumerate(produtos_base):
                preco = precos[11 - mes_offset]
                # Variar quantidade um pouco
                qtd = qtd_base * Decimal(str(random.uniform(0.8, 1.2)))
                itens_nota.append((nome, unidade, qtd, preco))
            
            # Adicionar produtos esporádicos (às vezes)
            for nome, unidade, qtd_base, precos in produtos_esporadicos:
                preco = precos[11 - mes_offset]
                if preco is not None:  # Só adiciona se tem preço definido
                    itens_nota.append((nome, unidade, qtd_base, preco))
            
            # Criar e salvar nota
            chave_base = f"{mes_offset:02d}{nota_idx:02d}{''.zfill(30)}"
            estabelecimento = random.choice(estabelecimentos)
            
            nota = criar_nota_teste(chave_base, data_mes, estabelecimento, itens_nota)
            salvar_nota(nota)
            
            # Classificar itens
            itens_classificacao = []
            for idx, item in enumerate(nota.itens, 1):
                # Determinar categoria baseado no produto
                if "Arroz" in item.descricao or "Feijão" in item.descricao or "Açúcar" in item.descricao:
                    categoria = "Alimentos básicos"
                elif "Carne" in item.descricao or "Frango" in item.descricao:
                    categoria = "Carnes e ovos"
                elif "Leite" in item.descricao:
                    categoria = "Laticínios"
                elif "Óleo" in item.descricao:
                    categoria = "Óleos e gorduras"
                elif "Macarrão" in item.descricao:
                    categoria = "Massas"
                elif "Café" in item.descricao:
                    categoria = "Bebidas"
                elif "Tomate" in item.descricao:
                    categoria = "Hortifruti"
                elif "Chocolate" in item.descricao or "Vinho" in item.descricao:
                    categoria = "Extras"
                else:
                    categoria = "Outros"
                
                # Extrair nome do produto (primeira parte antes de qualquer modificador)
                produto_nome = item.descricao.split()[0] + (" " + item.descricao.split()[1] if len(item.descricao.split()) > 1 else "")
                
                itens_classificacao.append({
                    "chave_acesso": nota.chave_acesso,
                    "sequencia": idx,
                    "categoria": categoria,
                    "produto_nome": produto_nome,
                    "produto_marca": None,
                    "origem": "seed_test",
                    "modelo": "manual",
                    "confianca": 1.0,
                    "confirmar": True,
                })
            
            registrar_classificacao_itens(itens_classificacao, confirmar=True)
            
            print(f"  ✓ Nota {nota.chave_acesso} criada com {len(itens_nota)} itens")
    
    print("\n✅ Dados de teste criados com sucesso!")
    print(f"   - 12 meses de dados")
    print(f"   - {len(produtos_base)} produtos regulares")
    print(f"   - {len(produtos_esporadicos)} produtos esporádicos")
    print(f"   - Aproximadamente 24-36 notas fiscais")


if __name__ == "__main__":
    popular_dados_teste()
