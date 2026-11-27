"""Doubles das fronteiras para os testes de unidade do serviço (US03)."""

from app.notificacoes.schemas import Inscricao, PaginaNotificacoes


class InscricoesFake:
    """Guarda as inscrições em memória."""

    def __init__(self):
        self.dados = {}

    def adicionar(self, nova):
        insc = Inscricao(
            id=len(self.dados) + 1,
            usuario_id=nova.usuario_id,
            ocorrencia_id=nova.ocorrencia_id,
            categoria_id=nova.categoria_id,
            centro=nova.centro,
            raio_metros=nova.raio_metros,
        )
        self.dados[insc.id] = insc
        return insc

    def listar(self, usuario_id):
        return [i for i in self.dados.values() if i.usuario_id == usuario_id]

    def obter(self, id_):
        return self.dados.get(id_)

    def remover(self, id_):
        self.dados.pop(id_, None)

    def segue_ocorrencia(self, usuario_id, ocorrencia_id):
        return any(
            i.usuario_id == usuario_id and i.ocorrencia_id == ocorrencia_id
            for i in self.dados.values()
        )


class StatusFake:
    """Status das ocorrências em memória, com o log das transições."""

    def __init__(self, status=None):
        self.status = dict(status or {})
        self.transicoes = []

    def status_de(self, ocorrencia_id):
        return self.status.get(ocorrencia_id)

    def registrar_transicao(self, ocorrencia_id, anterior, novo, quando):
        self.status[ocorrencia_id] = novo
        self.transicoes.append((ocorrencia_id, anterior, novo, quando))


class FonteFake:
    """Devolve uma página fixa e guarda os argumentos recebidos."""

    def __init__(self):
        self.chamadas = []

    def listar(self, usuario_id, limite, offset):
        self.chamadas.append((usuario_id, limite, offset))
        return PaginaNotificacoes(itens=[], proximo_offset=None)
