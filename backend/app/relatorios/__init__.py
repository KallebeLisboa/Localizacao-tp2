"""Relatório gerencial de atividades (US06).

Camadas:

* ``schemas``: filtro da consulta parametrizada e modelos do relatório.
* ``exportacao``: conversão do relatório para CSV.
* ``servico``: monta o relatório; depende só da interface ``FonteRelatorio``.
* ``repositorio_sql``: consultas de agregação no PostgreSQL/PostGIS.
* ``rotas``: ``APIRouter`` FastAPI, restrito a administradores.
"""
