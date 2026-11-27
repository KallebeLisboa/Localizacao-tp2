"""Interfaces de que o serviço de notificações depende."""

from datetime import datetime
from typing import Optional, Protocol

from app.models import StatusOcorrencia
from app.notificacoes.schemas import (
    Inscricao,
    NovaInscricao,
    PaginaNotificacoes,
)


class RepositorioInscricoes(Protocol):
    """Persistência das inscrições de alerta."""

    def adicionar(self, nova: NovaInscricao) -> Inscricao:
        """Persiste e devolve a inscrição com identificador."""

    def listar(self, usuario_id: int) -> list[Inscricao]:
        """Lista as inscrições do usuário, da mais antiga para a mais nova."""

    def obter(self, id_: int) -> Optional[Inscricao]:
        """Busca por identificador."""

    def remover(self, id_: int) -> None:
        """Remove a inscrição."""

    def segue_ocorrencia(self, usuario_id: int, ocorrencia_id: int) -> bool:
        """Indica se o usuário já segue a ocorrência."""


class RegistroStatus(Protocol):
    """Leitura e alteração do status de uma ocorrência, com log do evento."""

    def status_de(self, ocorrencia_id: int) -> Optional[StatusOcorrencia]:
        """Status atual, ou ``None`` se a ocorrência não existir."""

    def registrar_transicao(
        self,
        ocorrencia_id: int,
        anterior: StatusOcorrencia,
        novo: StatusOcorrencia,
        quando: datetime,
    ) -> None:
        """Atualiza o status e grava o ``LogEvento`` na mesma transação."""


class FonteNotificacoes(Protocol):
    """Consulta os eventos que interessam ao usuário."""

    def listar(self, usuario_id: int, limite: int, offset: int) -> PaginaNotificacoes:
        """Eventos de ocorrências seguidas ou dentro de uma zona assinada."""
