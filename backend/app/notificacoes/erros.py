"""Erros de domínio do módulo de notificações (US03).

Cada erro traz um ``codigo`` estável e o ``status_http`` correspondente, usados
pelas rotas para montar a resposta ``{"detail": {"codigo", "mensagem"}}``.
"""


class ErroNotificacao(Exception):
    """Base dos erros de regra de negócio deste módulo."""

    codigo = "erro_notificacao"
    status_http = 400


class OcorrenciaInexistente(ErroNotificacao):
    """A ocorrência informada não existe."""

    codigo = "ocorrencia_inexistente"
    status_http = 404


class CategoriaInexistente(ErroNotificacao):
    """A categoria informada na inscrição não existe."""

    codigo = "categoria_inexistente"
    status_http = 422


class InscricaoDuplicada(ErroNotificacao):
    """O usuário já segue esta ocorrência."""

    codigo = "inscricao_duplicada"
    status_http = 409


class InscricaoNaoEncontrada(ErroNotificacao):
    """Inscrição inexistente ou pertencente a outro usuário."""

    codigo = "inscricao_nao_encontrada"
    status_http = 404


class TransicaoInvalida(ErroNotificacao):
    """A mudança de status não respeita o ciclo de vida da ocorrência."""

    codigo = "transicao_invalida"
    status_http = 409
