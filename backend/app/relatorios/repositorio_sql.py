"""Consultas de agregação do relatório gerencial no PostgreSQL/PostGIS (US06)."""

from sqlalchemy import ColumnElement, and_, distinct, exists, func, select
from sqlalchemy.orm import Session

from app.models import (
    LogPesquisa,
    Ocorrencia,
    PerimetroAutorizado,
    StatusOcorrencia,
    Usuario,
)
from app.relatorios.schemas import (
    FORA_DAS_REGIOES,
    ChamadosPorRegiao,
    FiltroRelatorio,
    ResumoUsuarios,
    TermoPesquisado,
)


def _no_periodo(coluna, filtro: FiltroRelatorio) -> list[ColumnElement[bool]]:
    """Condições ``inicio <= coluna < fim`` para os limites informados."""
    condicoes = []
    if filtro.inicio is not None:
        condicoes.append(coluna >= filtro.inicio)
    if filtro.fim is not None:
        condicoes.append(coluna < filtro.fim)
    return condicoes


def _contagens_por_status():
    """Total e contagem por status das ocorrências do ``JOIN``."""
    oc = Ocorrencia
    return (
        func.count(oc.id),
        func.count(oc.id).filter(oc.status == StatusOcorrencia.REGISTRADO),
        func.count(oc.id).filter(oc.status == StatusOcorrencia.EM_ANALISE),
        func.count(oc.id).filter(oc.status == StatusOcorrencia.RESOLVIDO),
    )


def _linha_regiao(nome: str, total, registrado, em_analise, resolvido):
    return ChamadosPorRegiao(
        regiao=nome,
        total=total,
        registrado=registrado,
        em_analise=em_analise,
        resolvido=resolvido,
    )


class RepositorioRelatorioSQL:
    """Lê os dados consolidados direto das tabelas do sistema.

    Args:
        db: Sessão do banco.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def _contar(self, consulta) -> int:
        return int(self._db.scalar(consulta) or 0)

    def resumo_usuarios(self, filtro: FiltroRelatorio) -> ResumoUsuarios:
        """Contas ativas/inativas (hoje) e atividade no período."""
        contar = select(func.count()).select_from(Usuario)
        return ResumoUsuarios(
            contas_ativas=self._contar(contar.where(Usuario.ativo.is_(True))),
            contas_inativas=self._contar(contar.where(Usuario.ativo.is_(False))),
            novos_no_periodo=self._contar(
                contar.where(*_no_periodo(Usuario.criado_em, filtro))
            ),
            com_ocorrencia_no_periodo=self._contar(
                select(func.count(distinct(Ocorrencia.usuario_id))).where(
                    *_no_periodo(Ocorrencia.criado_em, filtro)
                )
            ),
        )

    def termos_mais_pesquisados(self, filtro: FiltroRelatorio) -> list[TermoPesquisado]:
        """Ranking de termos, sem diferenciar maiúsculas nem espaços nas pontas.

        Pesquisas sem termo (vazias ou só com espaços) são ignoradas. Empates
        ficam em ordem alfabética.
        """
        termo = func.lower(func.trim(LogPesquisa.termo_buscado))
        quantidade = func.count()
        consulta = (
            select(termo, quantidade)
            .where(
                LogPesquisa.termo_buscado.isnot(None),
                func.trim(LogPesquisa.termo_buscado) != "",
                *_no_periodo(LogPesquisa.pesquisado_em, filtro),
            )
            .group_by(termo)
            .order_by(quantidade.desc(), termo)
            .limit(filtro.limite_termos)
        )
        return [
            TermoPesquisado(termo=t, quantidade=q)
            for t, q in self._db.execute(consulta).all()
        ]

    def chamados_por_regiao(self, filtro: FiltroRelatorio) -> list[ChamadosPorRegiao]:
        """Ocorrências do período por região cadastrada, mais as de fora.

        Toda região aparece, mesmo sem chamados. A borda do polígono conta
        como dentro (``ST_Covers``), como no cadastro de ocorrências.
        """
        per, oc = PerimetroAutorizado, Ocorrencia
        dentro = func.ST_Covers(per.area, oc.localizacao)
        por_regiao = (
            select(per.nome_regiao, *_contagens_por_status())
            .select_from(per)
            .outerjoin(oc, and_(dentro, *_no_periodo(oc.criado_em, filtro)))
            .group_by(per.id, per.nome_regiao)
        )
        linhas = [_linha_regiao(*linha) for linha in self._db.execute(por_regiao)]

        em_alguma_regiao = exists().where(dentro)
        fora = select(*_contagens_por_status()).where(
            ~em_alguma_regiao, *_no_periodo(oc.criado_em, filtro)
        )
        linhas.append(_linha_regiao(FORA_DAS_REGIOES, *self._db.execute(fora).one()))
        return linhas
