from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional
import re

import httpx
from bs4 import BeautifulSoup, Tag

from src.logger import setup_logging

logger = setup_logging("scrapers.receita_rs")

SoupNode = Tag | BeautifulSoup

NFCE_POST_URL = "https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp"
NFCE_REFERER_TEMPLATE = (
    "https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_1.asp?chaveNFe={chave}"
)
RAW_HTML_DIR = Path(__file__).resolve().parents[2] / "data" / "raw_nfce"

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
}

_POST_HEADER_EXTRAS = {
    "Origin": "https://www.sefaz.rs.gov.br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "iframe",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Content-Type": "application/x-www-form-urlencoded",
}
_DIGITS_ONLY = re.compile(r"\D+")


@dataclass
class NotaItem:
    descricao: str
    codigo: Optional[str]
    quantidade: Decimal
    unidade: str
    valor_unitario: Decimal
    valor_total: Decimal


@dataclass
class Pagamento:
    forma: str
    valor: Decimal


@dataclass
class NotaFiscal:
    chave_acesso: str
    emitente_nome: Optional[str] = None
    emitente_cnpj: Optional[str] = None
    emitente_endereco: Optional[str] = None
    numero: Optional[str] = None
    serie: Optional[str] = None
    emissao: Optional[str] = None
    itens: List[NotaItem] = field(default_factory=list)
    total_itens: Optional[int] = None
    valor_total: Optional[Decimal] = None
    valor_pago: Optional[Decimal] = None
    pagamentos: List[Pagamento] = field(default_factory=list)
    tributos: Optional[Decimal] = None
    consumidor_cpf: Optional[str] = None
    consumidor_nome: Optional[str] = None


__all__ = [
    "validar_chave_acesso",
    "montar_url",
    "baixar_html",
    "buscar_nota",
    "carregar_nfce_de_arquivo",
    "parse_nota",
    "parse_nfce_html",
    "NotaFiscal",
    "NotaItem",
    "Pagamento",
]


def _normalize_chave(chave: str) -> str:
    digits = _DIGITS_ONLY.sub("", chave)
    if len(digits) != 44:
        raise ValueError("A chave de acesso deve conter 44 dígitos numéricos.")
    return digits


def validar_chave_acesso(chave: str) -> bool:
    try:
        _normalize_chave(chave)
        return True
    except ValueError:
        return False


def montar_url(chave: str) -> str:
    sanitized = _normalize_chave(chave)
    return NFCE_REFERER_TEMPLATE.format(chave=sanitized)


def baixar_html(
    chave: str,
    *,
    client: Optional[httpx.Client] = None,
    destino_html: Optional[Path] = None,
) -> str:
    chave_sanitizada = _normalize_chave(chave)
    referer = NFCE_REFERER_TEMPLATE.format(chave=chave_sanitizada)
    request_headers = {
        **_DEFAULT_HEADERS,
        **_POST_HEADER_EXTRAS,
        "Referer": referer,
    }
    payload = {"HML": "false", "chaveNFe": chave_sanitizada, "Action": "Avançar"}
    session = (
        client
        if client is not None
        else httpx.Client(timeout=30, headers=_DEFAULT_HEADERS, follow_redirects=True)
    )
    needs_close = client is None
    try:
        response = session.post(NFCE_POST_URL, data=payload, headers=request_headers)
        response.raise_for_status()
        html = response.text
        _persistir_html(chave_sanitizada, html, destino_html)
        logger.info(f"HTML baixado com sucesso para chave {chave_sanitizada}")
        return html
    except httpx.HTTPError as e:
        logger.error(f"Erro HTTP ao baixar nota {chave_sanitizada}: {e}")
        raise
    finally:
        if needs_close:
            session.close()


def buscar_nota(chave: str, *, client: Optional[httpx.Client] = None) -> NotaFiscal:
    html = baixar_html(chave, client=client)
    return parse_nfce_html(html)


def carregar_nfce_de_arquivo(caminho: Path | str) -> NotaFiscal:
    path = Path(caminho)
    html = path.read_text(encoding="utf-8")
    return parse_nfce_html(html)


def _persistir_html(chave: str, html: str, destino: Optional[Path]) -> Path:
    pasta = destino or RAW_HTML_DIR
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"nfce_{chave}.html"
    arquivo.write_text(html, encoding="utf-8")
    return arquivo


def parse_nota(html: str, chave: str) -> NotaFiscal:
    chave_sanitizada = _normalize_chave(chave)
    nota = parse_nfce_html(html)
    if nota.chave_acesso != chave_sanitizada:
        logger.error(f"Chave extraída ({nota.chave_acesso}) difere da solicitada ({chave_sanitizada})")
        raise ValueError("A chave fornecida não confere com a chave presente no HTML.")
    logger.info(f"Nota parseada com sucesso: {nota.valor_total} ({len(nota.itens)} itens)")
    return nota


def parse_nfce_html(html: str) -> NotaFiscal:
    soup = BeautifulSoup(html, "html.parser")
    chave = _parse_chave(soup)
    emitente_nome, emitente_cnpj, emitente_endereco = _parse_estabelecimento(soup)
    consumidor_cpf, consumidor_nome = _parse_consumidor(soup)
    itens = _parse_itens(soup)
    numero_itens = _parse_numero_itens(soup)
    numero, serie, emissao = _parse_informacoes_gerais(soup)
    valor_total, tributos, formas = _parse_blocos_totais(soup)

    if valor_total is None:
        valor_total = sum((item.valor_total for item in itens), Decimal("0"))

    pagamentos = [Pagamento(forma=forma, valor=valor) for forma, valor in formas.items()]
    valor_pago: Optional[Decimal] = None
    if pagamentos:
        acumulado = Decimal("0")
        for pagamento in pagamentos:
            acumulado += pagamento.valor
        valor_pago = acumulado

    return NotaFiscal(
        chave_acesso=chave,
        emitente_nome=emitente_nome,
        emitente_cnpj=emitente_cnpj,
        emitente_endereco=emitente_endereco,
        numero=numero,
        serie=serie,
        emissao=emissao,
        itens=itens,
        total_itens=numero_itens,
        valor_total=valor_total,
        valor_pago=valor_pago,
        pagamentos=pagamentos,
        tributos=tributos,
        consumidor_cpf=consumidor_cpf,
        consumidor_nome=consumidor_nome,
    )


def _parse_chave(soup: BeautifulSoup) -> str:
    tag = soup.select_one("span.chave")
    if tag:
        texto = _DIGITS_ONLY.sub("", tag.get_text())
        if len(texto) == 44:
            return texto

    for trecho in soup.stripped_strings:
        somente_digitos = _DIGITS_ONLY.sub("", trecho)
        if len(somente_digitos) == 44:
            return somente_digitos

    raise ValueError("Não foi possível localizar a chave no HTML da NFC-e.")


def _parse_estabelecimento(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str], Optional[str]]:
    container = soup.select_one("div.txtCenter")
    if container:
        nome_tag = container.select_one("#u20")
        nome = nome_tag.get_text(strip=True) if nome_tag else ""

        textos = [div.get_text(" ", strip=True) for div in container.select("div.text")]
        cnpj = ""
        endereco_pieces: List[str] = []
        for texto in textos:
            if texto.startswith("CNPJ"):
                cnpj = texto.split(":", 1)[-1].strip()
            else:
                endereco_pieces.append(texto)
        endereco = " - ".join(endereco_pieces)
        return nome or None, cnpj or None, endereco or None

    nome_tag = soup.select_one("td.NFCCabecalho_SubTitulo")
    nome = nome_tag.get_text(" ", strip=True) if nome_tag else None

    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    for td in soup.select("td.NFCCabecalho_SubTitulo1"):
        texto = td.get_text(" ", strip=True)
        if "CNPJ" in texto and cnpj is None:
            cnpj = _extrair_cnpj(texto)
            continue
        if cnpj is not None and not endereco:
            endereco = texto

    if nome or cnpj or endereco:
        return nome, cnpj, endereco

    raise ValueError("Não foi possível localizar os dados do estabelecimento.")


def _parse_consumidor(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    for section in soup.select("div[data-role=collapsible]"):
        titulo = section.find("h4")
        if not titulo or "Consumidor" not in titulo.get_text(strip=True):
            continue
        cpf: Optional[str] = None
        nome: Optional[str] = None
        for li in section.select("li"):
            strong = li.find("strong")
            if not strong:
                continue
            rotulo = strong.get_text(strip=True).rstrip(":").strip()
            texto_completo = li.get_text(" ", strip=True)
            valor = texto_completo.replace(strong.get_text(strip=True), "", 1).strip()
            if rotulo.upper() == "CPF":
                cpf = valor
            elif rotulo.upper() == "NOME":
                nome = valor
        return cpf, nome
    return None, None


def _parse_itens(soup: BeautifulSoup) -> List[NotaItem]:
    """Extrai itens da nota fiscal.
    
    Suporta múltiplos layouts de NFC-e:
    1. Layout com divs/spans (txtTit, RCod, etc.)
    2. Layout com tabela NFCCabecalho e TDs NFCDetalhe_Item
    """
    # Tenta primeiro o layout moderno com spans
    linhas = soup.select("tr[id^=Item]")
    if not linhas:
        linhas = soup.select("div[id^=Item]")
    
    itens: List[NotaItem] = []
    
    # Layout 1: spans com classes específicas (txtTit, RCod, etc.)
    for linha in linhas:
        descricao_tag = linha.select_one("span.txtTit")
        if descricao_tag:
            descricao = descricao_tag.get_text(strip=True)
            codigo = _extract_codigo(linha.select_one("span.RCod"))
            quantidade = _decimal_from_label(linha.select_one("span.Rqtd"), "Qtde.")
            unidade = _extract_label(linha.select_one("span.RUN"), "UN") or ""
            valor_unitario = _decimal_from_label(linha.select_one("span.RvlUnit"), "Vl. Unit.")
            valor_total = _decimal_from_span(linha.select_one("span.valor"))

            itens.append(
                NotaItem(
                    descricao=descricao,
                    codigo=codigo,
                    quantidade=quantidade,
                    unidade=unidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total,
                )
            )
    
    # Se encontrou itens com o layout 1, retorna
    if itens:
        return itens
    
    # Layout 2: tabela com TDs classe NFCDetalhe_Item
    # Estrutura: tr[id="Item + N"] > td (código, descrição, qtde, un, vl_unit, vl_total)
    for linha in linhas:
        tds = linha.select("td.NFCDetalhe_Item")
        if len(tds) < 6:
            continue
        
        try:
            codigo = tds[0].get_text(strip=True) or None
            descricao = tds[1].get_text(strip=True)
            quantidade = _decimal_from_string(tds[2].get_text(strip=True))
            unidade = tds[3].get_text(strip=True)
            valor_unitario = _decimal_from_string(tds[4].get_text(strip=True))
            valor_total = _decimal_from_string(tds[5].get_text(strip=True))
            
            itens.append(
                NotaItem(
                    descricao=descricao,
                    codigo=codigo,
                    quantidade=quantidade,
                    unidade=unidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total,
                )
            )
        except (ValueError, InvalidOperation) as exc:
            logger.warning(f"Erro ao parsear item da linha {linha.get('id')}: {exc}")
            continue
    
    return itens


def _extract_codigo(tag: SoupNode | None) -> Optional[str]:
    if not tag:
        return None
    match = re.search(r"C[oó]digo:?\s*([0-9]+)", tag.get_text(), re.IGNORECASE)
    return match.group(1) if match else None


def _decimal_from_label(tag: SoupNode | None, label: str) -> Decimal:
    if not tag:
        raise ValueError(f"Etiqueta '{label}' não encontrada no HTML da nota.")
    match = re.search(rf"{re.escape(label)}\s*:?\s*([0-9.,]+)", tag.get_text(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Não foi possível extrair o valor de '{label}'.")
    return _decimal_from_string(match.group(1))


def _decimal_from_span(tag: SoupNode | None) -> Decimal:
    if not tag:
        raise ValueError("Valor total do item ausente.")
    return _decimal_from_string(tag.get_text())


def _extract_label(tag: SoupNode | None, label: str) -> Optional[str]:
    if not tag:
        return None
    match = re.search(rf"{re.escape(label)}\s*:?\s*([A-Za-z0-9]+)", tag.get_text(), re.IGNORECASE)
    return match.group(1) if match else None


def _decimal_from_string(valor: str) -> Decimal:
    texto = valor.strip().replace("\xa0", "").replace(" ", "")
    if not texto:
        raise ValueError("Valor numérico vazio.")
    without_thousands = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(without_thousands)
    except InvalidOperation as exc:
        raise ValueError(f"Não foi possível converter '{valor}' em decimal.") from exc


def _parse_informacoes_gerais(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str], Optional[str]]:
    numero: Optional[str] = None
    serie: Optional[str] = None
    emissao: Optional[str] = None

    header: Optional[Tag] = None
    for candidato in soup.select("h4"):
        titulo = candidato.get_text(strip=True).lower()
        if "informações gerais" in titulo:
            header = candidato
            break
    if header is None:
        return numero, serie, emissao

    info_li = header.find_next("li")
    if not info_li:
        return numero, serie, emissao

    texto = info_li.get_text(" ", strip=True)
    numero_match = re.search(r"Número:\s*([0-9]+)", texto)
    serie_match = re.search(r"Série:\s*([0-9]+)", texto)
    emissao_match = re.search(r"Emissão:\s*([^\-]+)", texto)

    if numero_match:
        numero = numero_match.group(1)
    if serie_match:
        serie = serie_match.group(1)
    if emissao_match:
        emissao = emissao_match.group(1).strip()

    return numero, serie, emissao


def _extrair_cnpj(texto: str) -> Optional[str]:
    match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    if match:
        return match.group(0)
    digits = _DIGITS_ONLY.sub("", texto)
    if len(digits) != 14:
        return None
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _parse_numero_itens(soup: BeautifulSoup) -> Optional[int]:
    for bloco in soup.select("#totalNota > div"):
        label = bloco.find("label")
        span = bloco.find("span", class_="totalNumb")
        if not label or not span:
            continue
        texto = label.get_text(strip=True)
        if "Qtd" in texto:
            somente_digitos = _DIGITS_ONLY.sub("", span.get_text())
            if somente_digitos:
                return int(somente_digitos)
    return None


def _parse_blocos_totais(soup: BeautifulSoup) -> tuple[Optional[Decimal], Optional[Decimal], Dict[str, Decimal]]:
    total: Optional[Decimal] = None
    tributos: Optional[Decimal] = None
    formas: Dict[str, Decimal] = {}
    for bloco in soup.select("#totalNota > div"):
        label = bloco.find("label")
        span = bloco.find("span", class_="totalNumb")
        if not label or not span:
            continue
        texto_label = label.get_text(strip=True)
        if "Valor a pagar" in texto_label:
            total = _decimal_from_string(span.get_text())
            continue
        if "Tributos" in texto_label:
            try:
                tributos = _decimal_from_string(span.get_text())
            except ValueError:
                pass
            continue
        if texto_label and not texto_label.startswith("Qtd") and not texto_label.startswith("Forma de pagamento"):
            try:
                valor = _decimal_from_string(span.get_text())
            except ValueError:
                continue
            formas[texto_label] = valor
    return total, tributos, formas