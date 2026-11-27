"""Filtros de consulta de ocorrências (US02)."""

from typing import Annotated, Optional

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import StatusOcorrencia
from app.ocorrencias.geo import CoordenadaInvalida, RetanguloMapa

LIMITE_PADRAO = 100
LIMITE_MAX = 500
#: Tamanho máximo do texto de busca (a coluna do log aceita 150).
BUSCA_MAX = 100

#: Estados exibidos no mapa quando nenhum status é pedido (US02: "ativas").
STATUS_ATIVOS = frozenset({StatusOcorrencia.REGISTRADO, StatusOcorrencia.EM_ANALISE})

Categorias = Annotated[frozenset[int], Field(min_length=1)]
Estados = Annotated[frozenset[StatusOcorrencia], Field(min_length=1)]
Busca = Annotated[str, StringConstraints(strip_whitespace=True, max_length=BUSCA_MAX)]


class FiltroOcorrencias(BaseModel):
    """Critérios combinados por interseção (todos precisam ser atendidos).

    Aceita valores textuais, como chegam em parâmetros de query.

    Attributes:
        categorias: Categorias aceitas; ``None`` = todas.
        status: Estados aceitos; ``None`` = :data:`STATUS_ATIVOS`.
        inicio: Data/hora inicial, inclusiva, com fuso obrigatório.
        fim: Data/hora final, exclusiva, com fuso obrigatório.
        sul: Borda sul do retângulo do mapa (inclusiva).
        oeste: Borda oeste do retângulo do mapa (inclusiva).
        norte: Borda norte do retângulo do mapa (inclusiva).
        leste: Borda leste do retângulo do mapa (inclusiva).
        busca: Texto procurado no título e na descrição, sem diferenciar
            maiúsculas; vazio = sem busca.
        limite: Máximo de itens por página.
        offset: Quantos itens pular na ordem padrão.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    categorias: Optional[Categorias] = None
    status: Optional[Estados] = None
    inicio: Optional[AwareDatetime] = None
    fim: Optional[AwareDatetime] = None
    sul: Optional[float] = None
    oeste: Optional[float] = None
    norte: Optional[float] = None
    leste: Optional[float] = None
    busca: Optional[Busca] = None
    limite: Annotated[int, Field(ge=1, le=LIMITE_MAX)] = LIMITE_PADRAO
    offset: Annotated[int, Field(ge=0)] = 0

    @field_validator("busca")
    @classmethod
    def _busca_vazia_e_sem_busca(cls, valor: Optional[str]) -> Optional[str]:
        return valor or None

    @model_validator(mode="after")
    def _validar_combinacoes(self) -> "FiltroOcorrencias":
        if self.inicio is not None and self.fim is not None and self.inicio >= self.fim:
            raise ValueError("inicio deve ser anterior a fim")
        bordas = (self.sul, self.oeste, self.norte, self.leste)
        if None in bordas and any(b is not None for b in bordas):
            raise ValueError("informe sul, oeste, norte e leste juntos")
        try:
            self.retangulo
        except CoordenadaInvalida as exc:
            raise ValueError(str(exc)) from exc
        return self

    @property
    def retangulo(self) -> Optional[RetanguloMapa]:
        """Retângulo do mapa, se as quatro bordas foram informadas."""
        if None in (self.sul, self.oeste, self.norte, self.leste):
            return None
        return RetanguloMapa(
            sul=self.sul, oeste=self.oeste, norte=self.norte, leste=self.leste
        )

    @property
    def status_efetivos(self) -> frozenset[StatusOcorrencia]:
        """Estados aplicados, com o padrão de ocorrências ativas."""
        return self.status if self.status is not None else STATUS_ATIVOS
