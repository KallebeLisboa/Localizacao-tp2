# Guia da API — Autenticação, Painel Admin (US05), Estatísticas (US04) e Relatório Gerencial (US06)

Backend em FastAPI sobre o PostgreSQL/PostGIS do projeto
(`backend/app/database.py`, `backend/app/models.py`). A documentação
interativa (Swagger) fica em `/docs`.

## Como rodar

```bash
docker compose up -d                 # na raiz do repositório: PostgreSQL + PostGIS
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m app.criar_admin "Admin" admin@unb.br Admin1234   # primeiro admin
uvicorn app.main:app --reload                             # http://localhost:8000/docs
```

As tabelas que faltarem são criadas ao subir a API (`create_all`, provisório
até o grupo adotar migrações). No Swagger, clique em **Authorize** e entre com
o e-mail (campo *username*) e a senha.

| Variável | Padrão | Para quê |
|---|---|---|
| `DATABASE_URL` | `postgresql://tp2_user:tp2_password@localhost:5432/ocorrencias_db` | Conexão com o banco |
| `SECRET_KEY` | chave de desenvolvimento | Assina os tokens. **Obrigatória em produção** |
| `JWT_EXPIRACAO_MIN` | `60` | Validade do token, em minutos |
| `BCRYPT_ROUNDS` | `12` | Custo do hash de senha |

## Testes e qualidade

Os mesmos passos do CI, rodados dentro de `backend/`. Os testes usam o PostGIS
do `docker compose`, e cada teste recria as tabelas.

```bash
black --check app tests
flake8 app tests
bandit -r app
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

## Endpoints

### Autenticação (`/auth`)
| Método | Rota | Quem | O que faz |
|---|---|---|---|
| POST | `/auth/registrar` | público | Cadastra usuário comum (ignora `is_admin` enviado) |
| POST | `/auth/login` | público | Formulário `username`/`password` → JWT Bearer |
| GET | `/auth/me` | logado | Dados do usuário do token |

### Usuários (`/usuarios`)
| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/usuarios?ativo=` | admin | Lista usuários |
| POST | `/usuarios` | admin | Cria usuário (pode criar outro admin com `is_admin`) |
| GET | `/usuarios/{id}` | o próprio ou admin | Consulta |
| PATCH | `/usuarios/{id}` | o próprio ou admin | Altera; `is_admin`/`ativo` só admin |
| DELETE | `/usuarios/{id}` | admin | **Inativa** (exclusão lógica) |

### Categorias — US05
| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/admin/categorias?ativa=` | admin | Lista todas |
| POST | `/admin/categorias` | admin | Cadastra |
| GET | `/admin/categorias/{id}` | admin | Consulta (inclusive inativa) |
| PATCH | `/admin/categorias/{id}` | admin | Altera nome/descrição |
| PATCH | `/admin/categorias/{id}/inativar` | admin | Inativa |
| PATCH | `/admin/categorias/{id}/reativar` | admin | Reativa |
| GET | `/categorias` | público | Só ativas (formulário da US01, filtros da US02) |
| GET | `/categorias/{id}` | público | Só se ativa |


### Ocorrências – US01 e US02 (`/ocorrencias`)
| Método | Rota | Quem | O que faz |
|---|---|---|---|
| POST | `/ocorrencias` | logado | Registra ocorrência georreferenciada (US01) |
| GET | `/ocorrencias` | público | Lista marcadores do mapa com filtros por categoria, status, datas, bounding box (`sul`, `oeste`, `norte`, `leste`) e texto (`busca`) (US02) |
| GET | `/ocorrencias/{ocorrencia_id}` | público | Consulta os detalhes completos de uma ocorrência (US02) |

**Busca por texto (`busca`):** procura o texto no título e na descrição, sem
diferenciar maiúsculas (acentos contam: "iluminação" não acha "iluminacao").
Espaços nas pontas são ignorados, busca vazia é o mesmo que não buscar, e o
limite é de 100 caracteres. `%` e `_` são procurados como texto comum.

Cada busca é **gravada automaticamente** em `logs_pesquisa`, a base do ranking
de termos do relatório gerencial (US06):

- grava o termo, o horário, o retângulo do mapa (`"sul,oeste,norte,leste"`,
  se informado) e quem buscou;
- a rota continua pública: com token válido, a busca fica associada ao
  usuário; sem token, ou com token inválido, ela é gravada como anônima;
- só a primeira página conta (`offset=0`), para a paginação não registrar a
  mesma busca várias vezes;
- consultas sem `busca` não são gravadas.

### Relatório gerencial — US06
| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/relatorios/gerencial` | admin | Dados consolidados de uso, em JSON ou CSV |

Parâmetros (todos opcionais):

| Parâmetro | Padrão | Para quê |
|---|---|---|
| `inicio` | sem limite | Início do período, inclusivo. Exige fuso: `2026-11-01T00:00:00-03:00` |
| `fim` | sem limite | Fim do período, **exclusivo**. Exige fuso |
| `limite_termos` | `10` | Tamanho do ranking de termos (1 a 50) |
| `formato` | `json` | `csv` devolve um arquivo para download |

O relatório tem três blocos:

- **`usuarios`:** `contas_ativas` e `contas_inativas` (situação de hoje, não
  dependem do período), `novos_no_periodo` e `com_ocorrencia_no_periodo`
  (usuários que registraram ao menos uma ocorrência no período).
- **`termos_mais_pesquisados`:** ranking da tabela `logs_pesquisa`, sem
  diferenciar maiúsculas nem espaços nas pontas; buscas vazias são ignoradas e
  empates ficam em ordem alfabética. A tabela é alimentada pelas buscas do
  mapa (`GET /ocorrencias?busca=...`).
- **`chamados_por_regiao`:** ocorrências do período em cada região de
  `perimetros_autorizados` (borda conta como dentro), com `total`,
  `registrado`, `em_analise` e `resolvido`. Toda região aparece, mesmo com
  zero; as ocorrências fora de todas as regiões ficam na linha
  "Fora das regiões cadastradas", sempre por último. Se regiões se sobrepõem,
  a ocorrência conta em cada uma.

O CSV é separado por `;` e salvo em UTF-8 com BOM, para o Excel em português
abrir em colunas e com acentos. Cada linha é um valor, com as colunas
`secao;item;metrica;valor`. Textos digitados por usuários que começam com
`=`, `+`, `-` ou `@` recebem um apóstrofo na frente, para a planilha não os
executar como fórmula.

### Estatísticas — US04 (`/estatisticas`)
Rotas **públicas** (sem token), para os gráficos e o mapa de calor.

| Método | Rota | O que faz |
|---|---|---|
| GET | `/estatisticas/resumo` | Totais por status, resolvidas × pendentes e taxa de resolução |
| GET | `/estatisticas/evolucao` | Quantidade por dia, semana ou mês (série para gráfico de linha) |
| GET | `/estatisticas/regioes` | Resolvidas × pendentes em cada região cadastrada |
| GET | `/estatisticas/sazonalidade` | Distribuição por mês do ano, dia da semana ou hora do dia |
| GET | `/estatisticas/reincidencia` | Locais com ocorrências repetidas (pontos para o mapa de calor) |

Filtros aceitos por todas as rotas (todos opcionais):

| Parâmetro | Para quê |
|---|---|
| `inicio` | Início do período, inclusivo. Exige fuso: `2026-11-01T00:00:00-03:00` |
| `fim` | Fim do período, **exclusivo**. Exige fuso |
| `regiao_id` | Só ocorrências dentro desta região (`perimetros_autorizados`); 404 se não existir |
| `categorias` | Só estas categorias; repita o parâmetro: `?categorias=1&categorias=2` |

Parâmetros de cada rota:

| Rota | Parâmetro | Padrão | Valores |
|---|---|---|---|
| `evolucao` | `granularidade` | `dia` | `dia`, `semana` (começa na segunda), `mes` |
| `sazonalidade` | `por` | `mes` | `mes`, `dia_semana` (1 = segunda … 7 = domingo), `hora` |
| `reincidencia` | `celula_m` | `500` | Lado da célula da grade, de 50 a 50 000 metros |
| `reincidencia` | `minimo` | `2` | Ocorrências mínimas para um local aparecer |
| `reincidencia` | `limite` | `50` | Quantos locais devolver (1 a 500) |

Todas as contagens trazem `total`, `resolvidas` e `pendentes`
(pendentes = registradas + em análise). Detalhes:

- **Fuso:** dia, semana, mês e hora seguem o horário de Brasília
  (`America/Sao_Paulo`), não o UTC. Uma ocorrência às 23h30 de Brasília conta
  naquele dia, mesmo já sendo o dia seguinte em UTC.
- **Sem buracos nos gráficos:** a evolução traz todos os períodos do intervalo
  (os vazios com zero) e a sazonalidade traz todas as chaves (12 meses, 7 dias
  ou 24 horas). Sem `inicio`/`fim`, a evolução vai do primeiro ao último
  período com dados. Séries com mais de 1000 pontos retornam **400**: use uma
  granularidade maior ou um intervalo menor.
- **`taxa_resolucao`** (no resumo) vai de 0 a 1, com 4 casas; é `null` quando
  não há ocorrências.
- **Regiões:** maior total primeiro; regiões sem ocorrências aparecem com
  zero; as ocorrências fora de todas as regiões ficam na última linha, com
  `regiao_id` nulo.
- **Reincidência:** o PostGIS junta as ocorrências numa grade de células de
  `celula_m` metros (`ST_SnapToGrid` em metros) e devolve, para cada célula com
  pelo menos `minimo` ocorrências, o ponto médio (`latitude`, `longitude`) e as
  contagens. Ordem: maior total primeiro.

Exemplo:

```bash
curl "http://localhost:8000/estatisticas/evolucao?granularidade=mes&inicio=2026-01-01T00:00:00-03:00"
```

```json
{"granularidade": "mes", "fuso": "America/Sao_Paulo",
 "pontos": [{"periodo": "2026-01-01", "total": 4, "resolvidas": 1, "pendentes": 3}, ...]}
```

## Decisões de projeto

- **Administrador:** é o campo `is_admin` do modelo `Usuario`. O cadastro
  público nunca cria admin; o primeiro vem do comando `criar_admin`.
- **Exclusão lógica:** nada é apagado. Usuários têm a coluna `ativo`
  (acrescentada ao modelo) e categorias a coluna `ativa`, para que ocorrências
  antigas continuem apontando para registros válidos.
- **Senha:** bcrypt; de 8 a 72 caracteres, com letra e número.
- **Login:** a mesma mensagem para e-mail inexistente e senha errada, com tempo
  de resposta parecido, para não revelar quais e-mails estão cadastrados.
- **Nome de categoria único** sem diferenciar maiúsculas, contando as inativas.
- **Admin não pode remover o próprio acesso** (`is_admin` ou `ativo`), para o
  sistema não ficar sem administrador.
- **Datas em UTC**, com `Z` no final. As estatísticas (US04) agrupam por
  dia, semana, mês e hora no horário de Brasília.
- **Camadas:** `api/routes` (HTTP) → `services` (regras) → `models` (ORM). Os
  serviços levantam exceções de `app/core/exceptions.py`, que o `main.py`
  converte em HTTP.

## Para quem cria rotas novas

```python
from app.api.deps import AdminAtual, DbSession, UsuarioAtual

@router.post("/ocorrencias")         # qualquer usuário logado
def registrar(dados: OcorrenciaCriar, db: DbSession, usuario: UsuarioAtual): ...

@router.delete("/admin/algo/{id}")   # só admin
def apagar(id: int, db: DbSession, _admin: AdminAtual): ...
```

Fixtures em `tests/conftest.py`: `client`, `db_session`, `cidadao`, `admin`,
`headers_cidadao`, `headers_admin`, `criar_usuario(...)`, `criar_categoria(...)`
e a função `headers_de(usuario)`.

## Pendências

- **Perímetros geográficos (US05):** o modelo `PerimetroAutorizado` já existe;
  faltam as rotas para o admin cadastrá-los.
- **mypy:** o `app/models.py` usa o estilo `Column(...)`, e o mypy acusa
  incompatibilidade de tipos nos serviços. Migrar os modelos para o estilo
  `Mapped[...]` do SQLAlchemy 2.0 resolve.

## Histórico de commits (TDD)

Cada funcionalidade tem um commit de teste falhando (`[RED]`) seguido do
commit que o faz passar (`[GREEN]`).

**`feature/autenticacao`**
1. `chore`: dependências da autenticação e correção do `requirements.txt`
2. Teste 1 — hash bcrypt e JWT
3. Teste 2 — cadastro, login e `/auth/me`
4. Teste 3 — CRUD de usuários
5. Teste 4 — comando `criar_admin`
6. Teste 5 — datas em UTC
7. `docs`: este guia

**`feature/us05-categorias`** (criada a partir da anterior)
1. Teste 6 — US05 categorias
2. `docs`: guia com a US05

**`feature/us06-relatorio`**
1. `fix`: registro de ocorrência volta a gravar o primeiro evento (notificações)
2. Teste 7 — filtro da consulta parametrizada
3. Teste 8 — exportação em CSV
4. Teste 9 — montagem do relatório (serviço)
5. Teste 10 — consultas de agregação no PostGIS
6. Teste 11 — rota `/relatorios/gerencial`
7. `docs`: guia com a US06
8. Teste 12 — filtro `busca` no `GET /ocorrencias`
9. Teste 13 — busca no título e na descrição (PostGIS)
10. Teste 14 — serviço grava as buscas
11. Teste 15 — gravação em `logs_pesquisa`
12. Teste 16 — rota com usuário opcional e integração com o relatório
13. `docs`: busca e gravação das pesquisas

**`feature/us04-estatisticas`** (criada a partir da `feature/us06-relatorio`)
1. `chore`: pacote `tzdata` (fuso de Brasília também no Windows)
2. Teste 17 — filtro e modelos das estatísticas
3. Teste 18 — resumo e regiões (serviço)
4. Teste 19 — evolução no tempo (serviço)
5. Teste 20 — sazonalidade e reincidência (serviço)
6. Teste 21 — contagens por status, região e período no PostGIS
7. Teste 22 — sazonalidade e reincidência no PostGIS
8. Teste 23 — rotas `/estatisticas/*`
9. `docs`: guia com a US04
