"""Contagens das estatísticas no PostgreSQL/PostGIS (US04)."""

from collections import defaultdict
from datetime import date

from sqlalchemy import ColumnElement, Date, Integer, and_, cast, exists, func, select
from sqlalchemy.orm import Session, aliased

from app.estatisticas.schemas import (
    NOME_FUSO,
    Agrupamento,
    FiltroEstatisticas,
    Granularidade,
    PorStatus,
)
from app.estatisticas.servico import ContagemRegiao, GrupoReincidencia
from app.models import Ocorrencia, PerimetroAutorizado, StatusOcorrencia

_TRUNCAR = {
    Granularidade.DIA: "day",
    Granularidade.SEMANA: "week",  # o PostgreSQL começa a semana na segunda
    Granularidade.MES: "month",
}


_EXTRAIR = {
    Agrupamento.MES: "month",
    Agrupamento.DIA_SEMANA: "isodow",  # 1 = segunda ... 7 = domingo
    Agrupamento.HORA: "hour",
}

#: Projeção métrica (metros) usada para montar a grade de reincidência.
_SRID_METROS = 3857


def _hora_local():
    """Data/hora do registro no horário de Brasília (sem fuso)."""
    return func.timezone(NOME_FUSO, Ocorrencia.criado_em)


def _condicoes(filtro: FiltroEstatisticas) -> list[ColumnElement[bool]]:
    """Filtros comuns aplicados às ocorrências."""
    oc = Ocorrencia
    condicoes: list[ColumnElement[bool]] = []
    if filtro.inicio is not None:
        condicoes.append(oc.criado_em >= filtro.inicio)
    if filtro.fim is not None:
        condicoes.append(oc.criado_em < filtro.fim)
    if filtro.categorias is not None:
        condicoes.append(oc.categoria_id.in_(filtro.categorias))
    if filtro.regiao_id is not None:
        regiao = aliased(PerimetroAutorizado)
        condicoes.append(
            exists().where(
                regiao.id == filtro.regiao_id,
                func.ST_Covers(regiao.area, oc.localizacao),
            )
        )
    return condicoes


def _por_status(linhas) -> dict[StatusOcorrencia, int]:
    """``[(status, n), ...]`` → ``{status: n}``, sem os status nulos."""
    return {status: n for status, n in linhas if status is not None}


class RepositorioEstatisticasSQL:
    """Lê as contagens direto da tabela ``ocorrencias``.

    A borda de uma região conta como dentro (``ST_Covers``), como no cadastro
    de ocorrências.

    Args:
        db: Sessão do banco.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def regiao_existe(self, regiao_id: int) -> bool:
        """Indica se a região está cadastrada."""
        return self._db.get(PerimetroAutorizado, regiao_id) is not None

    def contar_por_status(self, filtro: FiltroEstatisticas) -> PorStatus:
        """Quantidade de ocorrências em cada status."""
        consulta = (
            select(Ocorrencia.status, func.count())
            .where(*_condicoes(filtro))
            .group_by(Ocorrencia.status)
        )
        return _por_status(self._db.execute(consulta).all())

    def contar_por_regiao(self, filtro: FiltroEstatisticas) -> list[ContagemRegiao]:
        """Contagem por status em cada região e, sem filtro de região, fora.

        Toda região aparece, mesmo sem ocorrências.
        """
        per, oc = PerimetroAutorizado, Ocorrencia
        consulta = (
            select(per.id, per.nome_regiao, oc.status, func.count(oc.id))
            .select_from(per)
            .outerjoin(
                oc,
                and_(func.ST_Covers(per.area, oc.localizacao), *_condicoes(filtro)),
            )
            .group_by(per.id, per.nome_regiao, oc.status)
            .order_by(per.id)
        )
        if filtro.regiao_id is not None:
            consulta = consulta.where(per.id == filtro.regiao_id)
        nomes: dict[int, str] = {}
        contagens: dict[int, dict[StatusOcorrencia, int]] = defaultdict(dict)
        for regiao_id, nome, status, n in self._db.execute(consulta):
            nomes[regiao_id] = nome
            if status is not None:
                contagens[regiao_id][status] = n
        itens = [ContagemRegiao(i, nomes[i], contagens[i]) for i in nomes]

        if filtro.regiao_id is None:
            em_alguma = exists().where(func.ST_Covers(per.area, oc.localizacao))
            fora = (
                select(oc.status, func.count())
                .where(~em_alguma, *_condicoes(filtro))
                .group_by(oc.status)
            )
            por_status = _por_status(self._db.execute(fora).all())
            itens.append(ContagemRegiao(None, "", por_status))
        return itens

    def contar_por_periodo(
        self, filtro: FiltroEstatisticas, granularidade: Granularidade
    ) -> dict[date, PorStatus]:
        """Contagem por status em cada período, no horário de Brasília."""
        periodo = cast(func.date_trunc(_TRUNCAR[granularidade], _hora_local()), Date)
        consulta = (
            select(periodo, Ocorrencia.status, func.count())
            .where(*_condicoes(filtro))
            .group_by(periodo, Ocorrencia.status)
        )
        resultado: dict[date, dict[StatusOcorrencia, int]] = defaultdict(dict)
        for dia, status, n in self._db.execute(consulta):
            resultado[dia][status] = n
        return dict(resultado)

    def contar_sazonal(
        self, filtro: FiltroEstatisticas, por: Agrupamento
    ) -> dict[int, PorStatus]:
        """Contagem por status por mês, dia da semana ISO ou hora (local)."""
        chave = cast(func.extract(_EXTRAIR[por], _hora_local()), Integer)
        consulta = (
            select(chave, Ocorrencia.status, func.count())
            .where(*_condicoes(filtro))
            .group_by(chave, Ocorrencia.status)
        )
        resultado: dict[int, dict[StatusOcorrencia, int]] = defaultdict(dict)
        for k, status, n in self._db.execute(consulta):
            resultado[k][status] = n
        return dict(resultado)

    def agrupar_reincidencia(
        self, filtro: FiltroEstatisticas, celula_m: int, minimo: int, limite: int
    ) -> list[GrupoReincidencia]:
        """Agrupa as ocorrências numa grade de células de ``celula_m`` metros.

        Devolve as células com pelo menos ``minimo`` ocorrências, da maior
        para a menor, com o centro médio dos pontos de cada uma.
        """
        oc = Ocorrencia
        celula = func.ST_SnapToGrid(
            func.ST_Transform(oc.localizacao, _SRID_METROS), celula_m
        )
        centro = func.ST_Centroid(func.ST_Collect(oc.localizacao))
        latitude, longitude, total = func.ST_Y(centro), func.ST_X(centro), func.count()
        consulta = (
            select(
                latitude,
                longitude,
                func.count().filter(oc.status == StatusOcorrencia.REGISTRADO),
                func.count().filter(oc.status == StatusOcorrencia.EM_ANALISE),
                func.count().filter(oc.status == StatusOcorrencia.RESOLVIDO),
            )
            .where(*_condicoes(filtro))
            .group_by(celula)
            .having(total >= minimo)
            .order_by(total.desc(), latitude, longitude)
            .limit(limite)
        )
        return [
            GrupoReincidencia(
                latitude=lat,
                longitude=lon,
                por_status={
                    s: n
                    for s, n in (
                        (StatusOcorrencia.REGISTRADO, reg),
                        (StatusOcorrencia.EM_ANALISE, ana),
                        (StatusOcorrencia.RESOLVIDO, res),
                    )
                    if n
                },
            )
            for lat, lon, reg, ana, res in self._db.execute(consulta)
        ]
