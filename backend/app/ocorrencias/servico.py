"""Casos de uso de cadastro e consulta de ocorrências (US01 e US02)."""

from datetime import datetime, timezone
from typing import Optional

from app.models import StatusOcorrencia
from app.ocorrencias.erros import (
    CategoriaInativa,
    CategoriaInexistente,
    ForaDaAreaAutorizada,
    NaoAutenticado,
    OcorrenciaNaoEncontrada,
)
from app.ocorrencias.filtros import FiltroOcorrencias
from app.ocorrencias.geo import Ponto, RetanguloMapa
from app.ocorrencias.portas import (
    CatalogoCategorias,
    Pagina,
    Pesquisa,
    PoliticaArea,
    RegistroPesquisas,
    Relogio,
    RepositorioOcorrencias,
    SituacaoCategoria,
)
from app.ocorrencias.schemas import NovaOcorrencia, Ocorrencia, OcorrenciaEntrada


def agora_utc() -> datetime:
    """Relógio padrão, sempre em UTC."""
    return datetime.now(timezone.utc)


def _descrever_regiao(ret: Optional[RetanguloMapa]) -> Optional[str]:
    """Texto curto do retângulo do mapa, para o log de pesquisas."""
    if ret is None:
        return None
    return f"{ret.sul:.4f},{ret.oeste:.4f},{ret.norte:.4f},{ret.leste:.4f}"


class ServicoOcorrencias:
    """Aplica as regras de negócio e delega a persistência.

    Args:
        repositorio: Persistência das ocorrências.
        categorias: Catálogo de categorias (módulo administrativo).
        areas: Política de perímetros autorizados (módulo administrativo).
        relogio: Fonte de data/hora com fuso; padrão UTC.
        pesquisas: Onde gravar as buscas por texto (US06); ``None`` = não
            grava.
    """

    def __init__(
        self,
        repositorio: RepositorioOcorrencias,
        categorias: CatalogoCategorias,
        areas: PoliticaArea,
        relogio: Relogio = agora_utc,
        pesquisas: Optional[RegistroPesquisas] = None,
    ) -> None:
        self._repo = repositorio
        self._categorias = categorias
        self._areas = areas
        self._relogio = relogio
        self._pesquisas = pesquisas

    def registrar(
        self, usuario_id: Optional[int], entrada: OcorrenciaEntrada
    ) -> Ocorrencia:
        """Registra uma ocorrência (US01).

        Args:
            usuario_id: Usuário vindo da autenticação, nunca do corpo.
            entrada: Dados já validados pelo schema.

        Returns:
            A ocorrência persistida, com status ``REGISTRADO``.

        Raises:
            NaoAutenticado: Sem usuário autenticado.
            CategoriaInexistente: Categoria não cadastrada.
            CategoriaInativa: Categoria inativada pelo administrador.
            ForaDaAreaAutorizada: Ponto fora dos perímetros autorizados.
            ValueError: Relógio configurado sem fuso horário.
        """
        if usuario_id is None:
            raise NaoAutenticado("autenticação necessária para registrar")

        situacao = self._categorias.situacao(entrada.categoria_id)
        if situacao is SituacaoCategoria.INEXISTENTE:
            raise CategoriaInexistente(f"categoria {entrada.categoria_id} não existe")
        if situacao is SituacaoCategoria.INATIVA:
            raise CategoriaInativa(f"categoria {entrada.categoria_id} está inativa")

        ponto = Ponto(latitude=entrada.latitude, longitude=entrada.longitude)
        if not self._areas.ponto_autorizado(ponto):
            raise ForaDaAreaAutorizada("local fora das áreas atendidas")

        momento = self._relogio()
        if momento.utcoffset() is None:
            raise ValueError("o relógio deve fornecer data/hora com fuso")

        return self._repo.adicionar(
            NovaOcorrencia(
                usuario_id=usuario_id,
                categoria_id=entrada.categoria_id,
                titulo=entrada.titulo,
                descricao=entrada.descricao,
                ponto=ponto,
                status=StatusOcorrencia.REGISTRADO,
                criado_em=momento,
            )
        )

    def detalhar(self, id_: int) -> Ocorrencia:
        """Busca uma ocorrência pelo identificador (US02).

        Raises:
            OcorrenciaNaoEncontrada: Identificador inexistente.
        """
        oc = self._repo.obter(id_)
        if oc is None:
            raise OcorrenciaNaoEncontrada(f"ocorrência {id_} não encontrada")
        return oc

    def consultar(
        self, filtro: FiltroOcorrencias, usuario_id: Optional[int] = None
    ) -> Pagina:
        """Lista ocorrências conforme os filtros combinados (US02).

        Uma busca por texto é gravada para o relatório gerencial (US06) só
        na primeira página, para a paginação não contar a mesma busca de novo.

        Args:
            filtro: Critérios da consulta.
            usuario_id: Quem consultou, se estiver autenticado.

        Raises:
            ValueError: Relógio configurado sem fuso horário.
        """
        pagina = self._repo.listar(filtro)
        if self._pesquisas is not None and filtro.busca and filtro.offset == 0:
            momento = self._relogio()
            if momento.utcoffset() is None:
                raise ValueError("o relógio deve fornecer data/hora com fuso")
            self._pesquisas.registrar(
                Pesquisa(
                    termo=filtro.busca,
                    usuario_id=usuario_id,
                    regiao=_descrever_regiao(filtro.retangulo),
                    momento=momento,
                )
            )
        return pagina
