"""Regras de negócio de acompanhamento e notificações (US03)."""

from datetime import datetime, timezone
from typing import Callable

from app.models import StatusOcorrencia
from app.notificacoes.erros import (
    CategoriaInexistente,
    InscricaoDuplicada,
    InscricaoNaoEncontrada,
    OcorrenciaInexistente,
    TransicaoInvalida,
)
from app.notificacoes.portas import (
    FonteNotificacoes,
    RegistroStatus,
    RepositorioInscricoes,
)
from app.notificacoes.schemas import (
    Inscricao,
    InscricaoEntrada,
    NovaInscricao,
    PaginaNotificacoes,
)
from app.ocorrencias.geo import Ponto
from app.ocorrencias.portas import CatalogoCategorias, SituacaoCategoria

# Ciclo de vida: cada ocorrência só avança para o estado seguinte.
CICLO = [
    StatusOcorrencia.REGISTRADO,
    StatusOcorrencia.EM_ANALISE,
    StatusOcorrencia.RESOLVIDO,
]


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class ServicoNotificacoes:
    """Inscrições, mudança de status com log e consulta de notificações.

    Args:
        inscricoes: Repositório das inscrições.
        status: Acesso ao status das ocorrências e ao log de eventos.
        fonte: Consulta das notificações do usuário.
        categorias: Catálogo de categorias (US05).
        relogio: Fornece a data/hora atual (injetável nos testes).
    """

    def __init__(
        self,
        inscricoes: RepositorioInscricoes,
        status: RegistroStatus,
        fonte: FonteNotificacoes,
        categorias: CatalogoCategorias,
        relogio: Callable[[], datetime] = _agora,
    ) -> None:
        self._inscricoes = inscricoes
        self._status = status
        self._fonte = fonte
        self._categorias = categorias
        self._relogio = relogio

    def inscrever(self, usuario_id: int, entrada: InscricaoEntrada) -> Inscricao:
        """Cria uma inscrição por ocorrência ou por zona.

        Raises:
            OcorrenciaInexistente: Se a ocorrência não existir.
            InscricaoDuplicada: Se o usuário já seguir a ocorrência.
            CategoriaInexistente: Se a categoria da zona não existir.
        """
        if entrada.ocorrencia_id is not None:
            if self._status.status_de(entrada.ocorrencia_id) is None:
                raise OcorrenciaInexistente("ocorrência não encontrada")
            if self._inscricoes.segue_ocorrencia(usuario_id, entrada.ocorrencia_id):
                raise InscricaoDuplicada("você já segue esta ocorrência")
            nova = NovaInscricao(usuario_id, entrada.ocorrencia_id, None, None, None)
            return self._inscricoes.adicionar(nova)

        if entrada.categoria_id is not None:
            situacao = self._categorias.situacao(entrada.categoria_id)
            if situacao is SituacaoCategoria.INEXISTENTE:
                raise CategoriaInexistente("categoria não encontrada")
        centro = Ponto(latitude=entrada.latitude, longitude=entrada.longitude)
        nova = NovaInscricao(
            usuario_id, None, entrada.categoria_id, centro, entrada.raio_metros
        )
        return self._inscricoes.adicionar(nova)

    def listar_inscricoes(self, usuario_id: int) -> list[Inscricao]:
        """Lista as inscrições do usuário."""
        return self._inscricoes.listar(usuario_id)

    def cancelar(self, usuario_id: int, inscricao_id: int) -> None:
        """Cancela uma inscrição do próprio usuário.

        Raises:
            InscricaoNaoEncontrada: Se não existir ou for de outro usuário
                (a resposta é a mesma, para não revelar inscrições alheias).
        """
        insc = self._inscricoes.obter(inscricao_id)
        if insc is None or insc.usuario_id != usuario_id:
            raise InscricaoNaoEncontrada("inscrição não encontrada")
        self._inscricoes.remover(inscricao_id)

    def alterar_status(
        self, ocorrencia_id: int, novo: StatusOcorrencia
    ) -> StatusOcorrencia:
        """Avança o status da ocorrência e registra o evento no log.

        Raises:
            OcorrenciaInexistente: Se a ocorrência não existir.
            TransicaoInvalida: Se ``novo`` não for o estado seguinte do ciclo.
        """
        atual = self._status.status_de(ocorrencia_id)
        if atual is None:
            raise OcorrenciaInexistente("ocorrência não encontrada")
        posicao = CICLO.index(atual)
        if posicao + 1 >= len(CICLO) or CICLO[posicao + 1] is not novo:
            raise TransicaoInvalida(
                f"não é possível passar de {atual.value} para {novo.value}"
            )
        self._status.registrar_transicao(ocorrencia_id, atual, novo, self._relogio())
        return novo

    def consultar(
        self, usuario_id: int, limite: int, offset: int
    ) -> PaginaNotificacoes:
        """Notificações do usuário, da mais recente para a mais antiga."""
        return self._fonte.listar(usuario_id, limite, offset)
