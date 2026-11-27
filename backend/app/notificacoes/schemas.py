"""Modelos de entrada, domínio e saída das notificações (US03)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import StatusOcorrencia
from app.ocorrencias.geo import Ponto
from app.ocorrencias.schemas import Latitude, Longitude

RAIO_MAX_METROS = 50_000.0  # 50 km; limite proposto para alertas por zona

RaioMetros = Annotated[float, Field(gt=0, le=RAIO_MAX_METROS, allow_inf_nan=False)]


class InscricaoEntrada(BaseModel):
    """Corpo do pedido de inscrição.

    Há dois modos, mutuamente exclusivos:

    * **Ocorrência**: apenas ``ocorrencia_id``.
    * **Zona**: ``latitude``, ``longitude`` e ``raio_metros``, com
      ``categoria_id`` opcional (sem ele, vale para qualquer tipo).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    ocorrencia_id: Optional[Annotated[int, Field(gt=0)]] = None
    categoria_id: Optional[Annotated[int, Field(gt=0)]] = None
    latitude: Optional[Latitude] = None
    longitude: Optional[Longitude] = None
    raio_metros: Optional[RaioMetros] = None

    @model_validator(mode="after")
    def _validar_modo(self) -> "InscricaoEntrada":
        """Garante que o pedido é de ocorrência ou de zona, nunca dos dois."""
        zona = (self.latitude, self.longitude, self.raio_metros)
        if self.ocorrencia_id is not None:
            if self.categoria_id is not None or any(v is not None for v in zona):
                raise ValueError(
                    "inscrição por ocorrência não aceita categoria nem zona"
                )
            return self
        if any(v is None for v in zona):
            raise ValueError(
                "informe ocorrencia_id ou latitude, longitude e raio_metros"
            )
        return self


@dataclass(frozen=True)
class NovaInscricao:
    """Inscrição validada, ainda sem identificador."""

    usuario_id: int
    ocorrencia_id: Optional[int]
    categoria_id: Optional[int]
    centro: Optional[Ponto]
    raio_metros: Optional[float]


@dataclass(frozen=True)
class Inscricao:
    """Inscrição persistida, independente do ORM."""

    id: int
    usuario_id: int
    ocorrencia_id: Optional[int]
    categoria_id: Optional[int]
    centro: Optional[Ponto]
    raio_metros: Optional[float]


class InscricaoSaida(BaseModel):
    """Inscrição devolvida pela API."""

    id: int
    tipo: str  # "ocorrencia" ou "zona"
    ocorrencia_id: Optional[int]
    categoria_id: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    raio_metros: Optional[float]

    @classmethod
    def de(cls, insc: Inscricao) -> "InscricaoSaida":
        """Cria a saída a partir da inscrição de domínio."""
        return cls(
            id=insc.id,
            tipo="ocorrencia" if insc.ocorrencia_id is not None else "zona",
            ocorrencia_id=insc.ocorrencia_id,
            categoria_id=insc.categoria_id,
            latitude=None if insc.centro is None else insc.centro.latitude,
            longitude=None if insc.centro is None else insc.centro.longitude,
            raio_metros=insc.raio_metros,
        )


class MudancaStatusEntrada(BaseModel):
    """Corpo do pedido de mudança de status (administrador)."""

    model_config = ConfigDict(extra="forbid")

    status: StatusOcorrencia


@dataclass(frozen=True)
class Notificacao:
    """Evento de mudança de status relevante para o usuário."""

    log_id: int
    ocorrencia_id: int
    titulo: str
    status_anterior: Optional[StatusOcorrencia]
    status_novo: StatusOcorrencia
    registrado_em: datetime


class NotificacaoSaida(BaseModel):
    """Notificação devolvida pela API."""

    log_id: int
    ocorrencia_id: int
    titulo: str
    status_anterior: Optional[StatusOcorrencia]
    status_novo: StatusOcorrencia
    registrado_em: datetime

    @classmethod
    def de(cls, n: Notificacao) -> "NotificacaoSaida":
        """Cria a saída a partir da notificação de domínio."""
        return cls(**vars(n))


@dataclass(frozen=True)
class PaginaNotificacoes:
    """Página de notificações, da mais recente para a mais antiga."""

    itens: list[Notificacao]
    proximo_offset: Optional[int]
