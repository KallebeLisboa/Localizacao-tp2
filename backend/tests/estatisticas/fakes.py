"""Fonte de dados falsa para os testes do serviço de estatísticas (US04)."""


class FonteFalsa:
    """Devolve dados prontos e guarda as chamadas recebidas."""

    def __init__(
        self,
        por_status=None,
        por_periodo=None,
        por_regiao=None,
        sazonal=None,
        reincidencia=None,
        regioes_existentes=(1, 2, 3),
    ):
        self.por_status = por_status or {}
        self.por_periodo = por_periodo or {}
        self.por_regiao = por_regiao or []
        self.sazonal = sazonal or {}
        self.reincidencia = reincidencia or []
        self.regioes_existentes = set(regioes_existentes)
        self.chamadas = []

    def regiao_existe(self, regiao_id):
        return regiao_id in self.regioes_existentes

    def contar_por_status(self, filtro):
        self.chamadas.append(("status", filtro))
        return self.por_status

    def contar_por_periodo(self, filtro, granularidade):
        self.chamadas.append(("periodo", filtro, granularidade))
        return self.por_periodo

    def contar_por_regiao(self, filtro):
        self.chamadas.append(("regiao", filtro))
        return self.por_regiao

    def contar_sazonal(self, filtro, por):
        self.chamadas.append(("sazonal", filtro, por))
        return self.sazonal

    def agrupar_reincidencia(self, filtro, celula_m, minimo, limite):
        self.chamadas.append(("reincidencia", filtro, celula_m, minimo, limite))
        return self.reincidencia
