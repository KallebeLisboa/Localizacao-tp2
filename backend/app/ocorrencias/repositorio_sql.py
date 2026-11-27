"""Adaptadores SQLAlchemy/PostGIS sobre os modelos de ``app.models``."""

from datetime import timezone
from typing import Optional

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models import Categoria, LogEvento, PerimetroAutorizado
from app.models import Ocorrencia as OcorrenciaModel
from app.ocorrencias.filtros import FiltroOcorrencias
from app.ocorrencias.geo import Ponto
from app.ocorrencias.portas import Pagina, SituacaoCategoria
from app.ocorrencias.schemas import NovaOcorrencia, Ocorrencia

SRID = 4326


def _ponto_sql(ponto: Ponto):
    """Expressão PostGIS do ponto, na ordem X = longitude, Y = latitude."""
    x, y = ponto.como_xy()
    return func.ST_SetSRID(func.ST_MakePoint(x, y), SRID)


def _para_dominio(modelo: OcorrenciaModel) -> Ocorrencia:
    """Converte o modelo ORM na ocorrência de domínio."""
    geom = to_shape(modelo.localizacao)
    return Ocorrencia(
        id=modelo.id,
        usuario_id=modelo.usuario_id,
        categoria_id=modelo.categoria_id,
        titulo=modelo.titulo,
        descricao=modelo.descricao,
        ponto=Ponto(latitude=geom.y, longitude=geom.x),
        status=modelo.status,
        criado_em=modelo.criado_em.astimezone(timezone.utc),
        foto_url=modelo.foto_url,
    )


class RepositorioSQL:
    """Persistência das ocorrências na tabela ``ocorrencias``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def adicionar(self, nova: NovaOcorrencia) -> Ocorrencia:
        """Insere a ocorrência e confirma a transação."""
        modelo = OcorrenciaModel(
            usuario_id=nova.usuario_id,
            categoria_id=nova.categoria_id,
            titulo=nova.titulo,
            descricao=nova.descricao,
            localizacao=from_shape(Point(*nova.ponto.como_xy()), srid=SRID),
            status=nova.status,
            criado_em=nova.criado_em,
            atualizado_em=nova.criado_em,
        )
        self._db.add(modelo)
        self._db.flush()
        # Primeiro evento do histórico: base das notificações de novos registros.
        self._db.add(
            LogEvento(
                ocorrencia_id=modelo.id,
                status_anterior=None,
                status_novo=nova.status,
                registrado_em=nova.criado_em,
            )
        )
        self._db.commit()
        self._db.refresh(modelo)
        return _para_dominio(modelo)

    def obter(self, id_: int) -> Optional[Ocorrencia]:
        """Busca por identificador."""
        modelo = self._db.get(OcorrenciaModel, id_)
        return None if modelo is None else _para_dominio(modelo)

    def listar(self, filtro: FiltroOcorrencias) -> Pagina:
        """Filtra no banco, ordena (recente primeiro, depois maior id) e pagina."""
        m = OcorrenciaModel
        consulta = select(m).where(m.status.in_(filtro.status_efetivos))
        if filtro.categorias is not None:
            consulta = consulta.where(m.categoria_id.in_(filtro.categorias))
        if filtro.inicio is not None:
            consulta = consulta.where(m.criado_em >= filtro.inicio)
        if filtro.fim is not None:
            consulta = consulta.where(m.criado_em < filtro.fim)
        ret = filtro.retangulo
        if ret is not None:
            envelope = func.ST_MakeEnvelope(
                ret.oeste, ret.sul, ret.leste, ret.norte, SRID
            )
            consulta = consulta.where(func.ST_Covers(envelope, m.localizacao))
        consulta = (
            consulta.order_by(m.criado_em.desc(), m.id.desc())
            .offset(filtro.offset)
            .limit(filtro.limite + 1)  # um a mais indica se há próxima página
        )
        modelos = self._db.scalars(consulta).all()
        tem_mais = len(modelos) > filtro.limite
        return Pagina(
            itens=[_para_dominio(mo) for mo in modelos[: filtro.limite]],
            proximo_offset=filtro.offset + filtro.limite if tem_mais else None,
        )


class CatalogoCategoriasSQL:
    """Lê a tabela ``categorias`` mantida pelo módulo administrativo."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def situacao(self, categoria_id: int) -> SituacaoCategoria:
        """Informa se a categoria existe e está ativa."""
        categoria = self._db.get(Categoria, categoria_id)
        if categoria is None:
            return SituacaoCategoria.INEXISTENTE
        if categoria.ativa:
            return SituacaoCategoria.ATIVA
        return SituacaoCategoria.INATIVA


class PerimetrosSQL:
    """Verifica o ponto contra ``perimetros_autorizados`` no PostGIS.

    A borda do polígono conta como dentro (``ST_Covers``).

    Args:
        db: Sessão do banco.
        permitir_sem_perimetros: Se ``True``, aceita qualquer ponto enquanto
            nenhum perímetro estiver cadastrado. Padrão ``False``: sem
            perímetro, nada é autorizado.
    """

    def __init__(self, db: Session, permitir_sem_perimetros: bool = False) -> None:
        self._db = db
        self._permitir_sem_perimetros = permitir_sem_perimetros

    def ponto_autorizado(self, ponto: Ponto) -> bool:
        """Indica se o ponto está em algum perímetro autorizado."""
        coberto = exists().where(
            func.ST_Covers(PerimetroAutorizado.area, _ponto_sql(ponto))
        )
        if self._db.scalar(select(coberto)):
            return True
        if self._permitir_sem_perimetros:
            algum = exists().where(PerimetroAutorizado.id.isnot(None))
            return not self._db.scalar(select(algum))
        return False
