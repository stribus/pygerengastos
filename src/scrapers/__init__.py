"""Módulo responsável pela extração de notas fiscais a partir da Receita Gaúcha."""

from .receita_rs import NotaFiscal, NotaItem, Pagamento, buscar_nota, parse_nota

__all__ = [
	"NotaFiscal",
	"NotaItem",
	"Pagamento",
	"buscar_nota",
	"parse_nota",
]
