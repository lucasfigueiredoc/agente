# AGENTS.md — Instruções permanentes para o OpenCode

## Integração por sessão DisplayQuest (2026-11-13)

Solicitada pelo usuário: o chat usa o login existente do DisplayQuest, sem conta
de serviço. Esta decisão substitui o ciclo de vida global e o Basic Auth descritos
abaixo para a integração web. `QUESTAI_INTEGRATION_TOKEN` (SecretStr, >=32 caracteres)
autentica os serviços; `X-DisplayQuest-Session` transporta somente os cookies de
sessão NextAuth entre backends. O MCP valida a sessão no DisplayQuest e encaminha
os cookies às rotas existentes, que continuam sendo a autoridade de autorização.
Um provedor MCP é composto em bootstrap por requisição e sempre encerrado ao final;
nenhuma ferramenta/cliente autenticado é compartilhado entre usuários. A camada de
aplicação permanece independente de HTTP e credenciais. Não há fallback para
`DISPLAY_QUEST_USER`/`DISPLAY_QUEST_PASSWORD`. O Streamlit anterior não envia sessão
e não acessa mais `/agent/messages`; a interface integrada é o painel do DisplayQuest.
`/health` indica disponibilidade da API e modo `user_session`, sem afirmar conexão
MCP global. Esta exceção é necessária para isolar as sessões sem persistência.

## Contexto do projeto

O **QuestAI** é um agente de IA conversacional para auxiliar no gerenciamento de projetos e atividades de um laboratório acadêmico universitário. O sistema de gerenciamento do laboratório **já existe** e é exposto por um **servidor MCP externo**, desenvolvido e executado separadamente. O QuestAI é apenas a interface conversacional (linguagem natural → ferramentas MCP → resposta).

**Nunca recrie o servidor MCP nem reimplemente suas ferramentas.**

## Stack obrigatória

- Python 3.12+ com layout `src/` (preservar).
- **uv exclusivamente** para ambiente e dependências. Proibido: pip direto, Poetry, Pipenv, Conda.
- **LangChain 1.x**: API de agentes vigente é `create_agent` de `langchain.agents`. Não usar APIs legadas (`create_react_agent`, `AgentExecutor`).
- **MCP**: integração oficial atual via extra `langchain[mcp]` (namespace `langchain.mcp`, classe `MCPAdapter`, construído sobre FastMCP). O pacote `langchain-mcp-adapters` (`MultiServerMCPClient`) é legado — usar apenas como fallback documentado se o beta quebrar.
- **FastAPI** para rotas HTTP; **Streamlit** para a interface web; **pydantic-settings** para configuração.
- Antes de recomendar APIs/versões, consultar a documentação oficial vigente (docs.langchain.com) — exemplos antigos podem não ser válidos.

## Arquitetura — Ports and Adapters

Regras de dependência (invioláveis):

- `domain/` não importa nada externo.
- `application/` importa apenas stdlib e pydantic. **Nunca** importar FastAPI, Streamlit, LangChain ou SDK/adapter MCP.
- `adapters/` podem importar `application/` (os contratos), nunca o contrário.
- `bootstrap.py` é o único ponto que conhece todas as implementações concretas (composição raiz).
- Portas de saída usam tipos opacos para ferramentas (`Sequence[object]`): o serviço não conhece tipos LangChain.

## Estrutura de diretórios

```text
src/questai/
├── domain/                      # vazio até surgir entidade real (não criar artefatos)
├── application/
│   ├── ports/inbound/agent_port.py        # AgentPort + AgentMessage/AgentReply
│   ├── ports/outbound/llm_port.py         # AgentEnginePort (run(messages, tools) -> str)
│   ├── ports/outbound/mcp_port.py         # ToolProviderPort (get_tools, is_connected)
│   └── services/agent_service.py          # AgentService implementa AgentPort
├── adapters/
│   ├── inbound/api/app.py                 # create_app() + lifespan (conexão MCP no startup)
│   ├── inbound/api/routes.py              # POST /agent/messages, GET /health
│   ├── inbound/api/schemas.py             # ChatRequest/ChatResponse (pydantic)
│   ├── inbound/web/streamlit_app.py       # UI; consome a API SOMENTE por HTTP (httpx)
│   ├── outbound/llm/llm_factory.py        # seleção de provedor/modelo por configuração
│   ├── outbound/agent/langchain_agent_engine.py  # AgentEnginePort via create_agent
│   └── outbound/mcp/mcp_adapter.py        # ToolProviderPort via MCPAdapter
├── config/settings.py           # pydantic-settings, lê .env
└── bootstrap.py                 # composição das dependências + create_app
```

## Convenções e decisões a preservar

- **API stateless**: o histórico de conversa viaja do cliente para a API a cada request. Sem checkpointer/persistência na v1. Histórico visual fica em `st.session_state` no Streamlit.
- **Streamlit não importa** LangChain, MCP ou componentes do backend — apenas HTTP via `httpx`, usando `API_BASE_URL`.
- **Ciclo de vida MCP**: conexão única estabelecida no lifespan da FastAPI (startup: `MCPAdapter` entra no contexto e `list_tools()` popula o catálogo; shutdown: encerra e libera). Ferramentas do `MCPAdapter` são reentrantes e permanecem chamáveis.
- **Erros**: erro reportado pelo servidor MCP (`isError=True`) vira `ToolMessage(status="error")` e o modelo se autocorrige — não interceptar. Falhas de transporte/sessão levantam exceção e devem ser tratadas nos exception handlers da API (HTTP 502 com corpo estruturado, nunca traceback cru).
- **Troca de provedor de LLM**: apenas por configuração (`LLM_PROVIDER`, `LLM_MODEL`). Nunca alterar `agent_service.py` ou `routes.py` para trocar provedor.
- **Não criar `mcp_manager.py`** enquanto houver um único servidor MCP: multi-servidor já é suportado pelo `MCPAdapter` via dict `MCPConfig` (`{"mcpServers": {...}}`).
- `domain/` permanece vazio até existir entidade/regra de negócio própria.
- Separação de responsabilidades: provedor LLM (`llm_factory`) ≠ orquestração do agente (`langchain_agent_engine`) ≠ adaptação de ferramentas MCP (`mcp_adapter`).

## Configuração e credenciais

- Variáveis canônicas (ver `.env.example`): `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_BASE_URL` (base URL de servidor OpenAI-compatible self-hosted; vazio = OpenAI oficial), `MCP_SERVER_URL` (HTTP) ou `MCP_SERVER_COMMAND`/`MCP_SERVER_ARGS` (stdio), `API_HOST`, `API_PORT`, `API_BASE_URL`, chave de provedor (`OPENAI_API_KEY`) e credenciais do DisplayQuest usadas no acesso via MCP (`DISPLAY_QUEST_USER`, `DISPLAY_QUEST_PASSWORD`).
- **Nunca commitar `.env`** (já no `.gitignore`). `.env.example` é o espelho sem valores reais.
- Não hardcodar URLs, portas, modelos ou chaves fora de `config/settings.py`.
- Coordenadas de infraestrutura e identificação de modelo (`LLM_MODEL`, `MCP_SERVER_URL`) são **obrigatórias no `.env`** — `settings.py` não deve carregar defaults desses campos (evita vazar IP/modelo no código versionado e evita default silencioso encobrindo config ausente). Defaults em código só para valores não sensíveis e neutros (`API_HOST=127.0.0.1`, `API_PORT=8000`, `LLM_PROVIDER=openai`, `LLM_TEMPERATURE=0.2`); `API_BASE_URL` é derivada de host/porta quando não definida.

## Comandos

```bash
uv add <pacote>                  # adicionar dependência (nunca pip install)
uv sync                          # sincronizar .venv com uv.lock
uv run uvicorn "questai.bootstrap:create_app" --factory --reload   # API
uv run streamlit run src/questai/adapters/inbound/web/streamlit_app.py  # UI
```

## Restrições de escopo

- Não adicionar banco de dados, autenticação, filas, cache externo ou observabilidade sem solicitação explícita.
- Não iniciar testes automatizados nesta fase (serão tratados em etapa futura própria).
- Mudanças arquiteturais exigem justificativa técnica clara e registro neste arquivo.
- Não alterar a estrutura de diretórios acima sem justificativa aprovada.

## Servidor MCP externo (RESPONDIDO PELO DESENVOLVEDOR)

Respostas fornecidas pelo desenvolvedor do servidor MCP. Esta seção substitui o antigo ponto pendente e **não bloqueia mais** a implementação dos adaptadores MCP (`adapters/outbound/mcp`).

- [x] **Transporte**: Streamable HTTP por URL. stdio **não** é exposto na fase 1.
- [x] **Endpoint**: `http://<host>:8787/mcp` (porta 8787, path `/mcp`). Na LAN, `<host>` é o IP da interface. Configurar via `MCP_SERVER_URL`.
- [x] **Headers**: `Content-Type: application/json` e `Accept: application/json, text/event-stream` (sem `Accept` válido a resposta é `406`). Somente `POST`: `GET` e `DELETE` em `/mcp` respondem `405` com `Allow: POST`.
- [x] **Health**: `GET http://<host>:8787/healthz`.
- [x] **Autenticação no MCP**: o cliente envia as credenciais do DisplayQuest (`DISPLAY_QUEST_USER`/`DISPLAY_QUEST_PASSWORD`, vindas do `.env`) no cabeçalho `Authorization: Basic` do transporte. Medido na build da branch `dev` (2026-10-27): o endpoint ainda **não** valida credencial de consumidor (autenticação de cliente é fase 2 do plano do servidor) e o MCP autentica no DisplayQuest com a conta de serviço do ambiente dele. O envio pelo cliente está implementado e é neutro até o servidor passar a exigir.
- [x] **Origin**: ausente é aceito; `Origin` fora da allow-list responde `403`.
- [x] **Protocolo**: suporta a era `2026-07-28` (caminho moderno, com `MCP-Protocol-Version`, `Mcp-Method` e `Mcp-Name` em `tools/call` e `resources/read`) e atende clientes 2025-era no fallback stateless (`protocolVersion` `2025-06-18` no `initialize`). Versão explícita desconhecida → `400` com `-32020`. Servidor **stateless**: `Mcp-Session-Id` não é emitido nem exigido. JSON inválido → `400`/`-32700`; método desconhecido → `-32601`; parâmetro inválido → `-32602`.
- [x] **Ferramentas**: 25 no contrato `mcp/tools.json` (nome, título, descrição, `inputSchema` JSON Schema, annotations `readOnlyHint`/`destructiveHint`, erros HTTP).
  - **Leitura (15)**: `people_list`, `people_statistics`, `leaderboard_get`, `project_list`, `project_get`, `project_overview`, `member_performance`, `task_list`, `global_progress_get`, `hours_get`, `work_sessions_list`, `weekly_hours_history_get`, `laboratory_schedule_get`, `weekly_report_list`, `technical_report_list`.
  - **Escrita (10)**: `project_create`, `project_update`, `deliverable_create`, `activity_create`, `activity_update`, `weekly_report_generate`, `weekly_report_bulk_generate`, `technical_report_save`, `technical_report_generate`, `technical_report_draft`.
- [x] **Recurso (1)**: `dq://projects/{projectId}/technical-reports/{reportId}/file?userId={userId}` via `resources/read` → DOCX em blob base64 (download **nunca** por tool).
- [x] **Convenções**: IDs inteiros positivos; datas `YYYY-MM-DD`; meses `YYYY-MM`. Sucesso devolve `structuredContent` + resumo em `content`; falha devolve `isError: true` com `structuredContent {status, code, message}`, onde `code` é um de: `invalid_input`, `upstream_auth_failed`, `upstream_unauthorized`, `upstream_forbidden`, `not_found`, `conflict`, `upstream_error`, `ai_unavailable`, `bucket_unavailable`, `internal_error`.

Implicações de implementação: usar `MCP_SERVER_URL` (Streamable HTTP) como transporte único, mantendo-o isolado em `mcp_adapter.py`/`settings.py`. Credenciais do DisplayQuest saem do cliente no `Authorization` (senha como `SecretStr`, nunca em log, `repr` ou mensagem de erro). Não depender de sessão (`Mcp-Session-Id`). O contrato detalhado de cada tool está em `mcp/tools.json` (fonte de verdade a consultar ao implementar/validar argumentos).
