"""Exportação estruturada do relatório gerencial em CSV (US06).

Formato "longo": cada linha é um valor, com as colunas ``secao``, ``item``,
``metrica`` e ``valor``. Assim todas as seções cabem num único arquivo e a
planilha pode ser filtrada ou virar tabela dinâmica sem retrabalho.

O separador é ``;``, que o Excel em português abre direto em colunas.
"""

import csv
import io
from collections.abc import Iterator

from app.relatorios.schemas import RelatorioGerencial

CABECALHO = ("secao", "item", "metrica", "valor")

# Texto que começa com estes caracteres vira fórmula ao abrir no Excel
# (injeção de CSV). O apóstrofo na frente faz a planilha tratar como texto.
_INICIO_DE_FORMULA = ("=", "+", "-", "@")


def _texto_seguro(texto: str) -> str:
    """Neutraliza texto vindo de usuários que seria lido como fórmula."""
    return "'" + texto if texto.startswith(_INICIO_DE_FORMULA) else texto


def _linhas(rel: RelatorioGerencial) -> Iterator[tuple[str, str, str, object]]:
    dados = rel.model_dump(mode="json")
    yield ("relatorio", "gerado_em", "", dados["gerado_em"])
    yield ("relatorio", "periodo_inicio", "", dados["periodo"]["inicio"] or "")
    yield ("relatorio", "periodo_fim", "", dados["periodo"]["fim"] or "")
    for metrica, valor in dados["usuarios"].items():
        yield ("usuarios", "", metrica, valor)
    for termo in rel.termos_mais_pesquisados:
        yield ("termos", _texto_seguro(termo.termo), "quantidade", termo.quantidade)
    for regiao in rel.chamados_por_regiao:
        nome = _texto_seguro(regiao.regiao)
        for metrica in ("total", "registrado", "em_analise", "resolvido"):
            yield ("regioes", nome, metrica, getattr(regiao, metrica))


def para_csv(rel: RelatorioGerencial) -> str:
    """Converte o relatório em texto CSV.

    Args:
        rel: Relatório já consolidado.

    Returns:
        O CSV completo, com cabeçalho, separado por ``;``.
    """
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
    escritor.writerow(CABECALHO)
    escritor.writerows(_linhas(rel))
    return saida.getvalue()
