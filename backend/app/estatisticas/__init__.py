"""Painel de estatísticas e análise temporal (US04).

Camadas:

* ``schemas``: filtro comum, opções e modelos das respostas.
* ``servico``: monta as estatísticas (zeros nos períodos vazios, rótulos,
  ordenação); depende só da interface ``FonteEstatisticas``.
* ``repositorio_sql``: contagens no PostgreSQL/PostGIS.
* ``rotas``: ``APIRouter`` FastAPI com as rotas públicas.
"""
