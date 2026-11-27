"""Adaptadores SQLAlchemy/PostGIS do módulo de notificações (US03)."""

from datetime import datetime, timezone
from typing import Optional

from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import InscricaoNotificacao, LogEvento, StatusOcorrencia
from app.models import Ocorrencia as OcorrenciaModel
from app.notificacoes.schemas import (
    Inscricao,
    NovaInscricao,
    Notificacao,
    PaginaNotificacoes,
)
from app.ocorrencias.geo import Ponto

SRID = 4326


def _para_inscricao(modelo: InscricaoNotificacao) -> Inscricao:
    """Converte o modelo ORM na inscrição de domínio."""
    centro = None
    if modelo.centro_alerta is not None:
        geom = to_shape(modelo.centro_alerta)
        centro = Ponto(latitude=geom.y, longitude=geom.x)
    return Inscricao(
        id=modelo.id,
        usuario_id=modelo.usuario_id,
        ocorrencia_id=modelo.ocorrencia_id,
        categoria_id=modelo.categoria_id,
        centro=centro,
        raio_metros=modelo.raio_metros,
    )


class RepositorioInscricoesSQL:
    """Persistência na tabela ``inscricoes_notificacao``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def adicionar(self, nova: NovaInscricao) -> Inscricao:
        """Insere a inscrição e confirma a transação."""
        centro = None
        if nova.centro is not None:
            centro = from_shape(Point(*nova.centro.como_xy()), srid=SRID)
        modelo = InscricaoNotificacao(
            usuario_id=nova.usuario_id,
            ocorrencia_id=nova.ocorrencia_id,
            categoria_id=nova.categoria_id,
            centro_alerta=centro,
            raio_metros=nova.raio_metros,
        )
        self._db.add(modelo)
        self._db.commit()
        self._db.refresh(modelo)
        return _para_inscricao(modelo)

    def listar(self, usuario_id: int) -> list[Inscricao]:
        """Lista as inscrições do usuário em ordem de criação."""
        consulta = (
            select(InscricaoNotificacao)
            .where(InscricaoNotificacao.usuario_id == usuario_id)
            .order_by(InscricaoNotificacao.id)
        )
        return [_para_inscricao(m) for m in self._db.scalars(consulta)]

    def obter(self, id_: int) -> Optional[Inscricao]:
        """Busca por identificador."""
        modelo = self._db.get(InscricaoNotificacao, id_)
        return None if modelo is None else _para_inscricao(modelo)

    def remover(self, id_: int) -> None:
        """Apaga a inscrição, se existir."""
        modelo = self._db.get(InscricaoNotificacao, id_)
        if modelo is not None:
            self._db.delete(modelo)
            self._db.commit()

    def segue_ocorrencia(self, usuario_id: int, ocorrencia_id: int) -> bool:
        """Indica se já existe inscrição do usuário nesta ocorrência."""
        consulta = select(InscricaoNotificacao.id).where(
            InscricaoNotificacao.usuario_id == usuario_id,
            InscricaoNotificacao.ocorrencia_id == ocorrencia_id,
        )
        return self._db.scalar(consulta.limit(1)) is not None


class RegistroStatusSQL:
    """Altera o status da ocorrência e grava o ``LogEvento``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def status_de(self, ocorrencia_id: int) -> Optional[StatusOcorrencia]:
        """Status atual, ou ``None`` se a ocorrência não existir."""
        modelo = self._db.get(OcorrenciaModel, ocorrencia_id)
        return None if modelo is None else modelo.status

    def registrar_transicao(
        self,
        ocorrencia_id: int,
        anterior: StatusOcorrencia,
        novo: StatusOcorrencia,
        quando: datetime,
    ) -> None:
        """Atualiza o status e grava o log numa única transação."""
        modelo = self._db.get(OcorrenciaModel, ocorrencia_id)
        modelo.status = novo
        self._db.add(
            LogEvento(
                ocorrencia_id=ocorrencia_id,
                status_anterior=anterior,
                status_novo=novo,
                registrado_em=quando,
            )
        )
        self._db.commit()


class FonteNotificacoesSQL:
    """Monta o feed a partir de ``logs_eventos`` e das inscrições.

    Um evento interessa ao usuário se ele segue a ocorrência **ou** se a
    ocorrência está dentro do raio de uma zona assinada (e, quando a zona
    define categoria, é dessa categoria). A distância é calculada sobre
    ``geography``, portanto o raio é em metros reais.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def listar(self, usuario_id: int, limite: int, offset: int) -> PaginaNotificacoes:
        """Eventos relevantes, do mais recente para o mais antigo."""
        log, oc, insc = LogEvento, OcorrenciaModel, InscricaoNotificacao
        na_zona = and_(
            insc.ocorrencia_id.is_(None),
            insc.centro_alerta.isnot(None),
            or_(insc.categoria_id.is_(None), insc.categoria_id == oc.categoria_id),
            func.ST_DWithin(
                cast(oc.localizacao, Geography),
                cast(insc.centro_alerta, Geography),
                insc.raio_metros,
            ),
        )
        interessa = (
            select(insc.id)
            .where(
                insc.usuario_id == usuario_id,
                or_(insc.ocorrencia_id == log.ocorrencia_id, na_zona),
            )
            .exists()
        )
        consulta = (
            select(log, oc.titulo)
            .join(oc, oc.id == log.ocorrencia_id)
            .where(interessa)
            .order_by(log.registrado_em.desc(), log.id.desc())
            .offset(offset)
            .limit(limite + 1)  # um a mais indica se há próxima página
        )
        linhas = self._db.execute(consulta).all()
        itens = [
            Notificacao(
                log_id=ev.id,
                ocorrencia_id=ev.ocorrencia_id,
                titulo=titulo,
                status_anterior=ev.status_anterior,
                status_novo=ev.status_novo,
                registrado_em=ev.registrado_em.astimezone(timezone.utc),
            )
            for ev, titulo in linhas[:limite]
        ]
        tem_mais = len(linhas) > limite
        return PaginaNotificacoes(
            itens=itens, proximo_offset=offset + limite if tem_mais else None
        )
