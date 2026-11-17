# TASKS.md — Planejamento de desenvolvimento do QuestAI

> Documento exclusivamente de planejamento. Nenhum código de aplicação foi implementado nesta etapa.
> Fonte de requisitos e decisões: `AGENTS.md`.

## 1. Visão geral das etapas

| Etapa | Objetivo | Tarefas | Condição de avanço |
|---|---|---|---|
| 1. Preparação | Dependências, configuração e proteção de credenciais | TASK-001 a TASK-003 | `uv sync` funciona; configuração central existe; `.env` ignorado |
| 2. Núcleo da arquitetura | Portas e serviço de aplicação sem dependências externas | TASK-004 a TASK-006 | Serviço orquestra LLM e ferramentas apenas por contratos |
| 3. Integrações de saída | Fábrica de LLM, motor LangChain e adaptador MCP | TASK-007 a TASK-009 | LLM selecionado por configuração; MCP conectado com catálogo |
| 4. Entrada HTTP e composição | Schemas, rotas, app/lifespan/erros e bootstrap | TASK-010 a TASK-013 | API sobe pelo comando do `AGENTS.md` e compõe todas as dependências |
| 5. Interface web | Chat Streamlit consumindo apenas a API | TASK-014 | Conversa multi-turno funcional via HTTP |
| 6. Validação integrada | Verificar a v1 de ponta a ponta | TASK-015 | Critérios gerais da v1 atendidos |

## 2. Estado atual do repositório

- `pyproject.toml` existe, mas está sem dependências declaradas.
- `src/questai/__init__.py` contém apenas um entrypoint provisório (`main`), sem relação com a arquitetura final.
- Não existem `src/questai/config/`, `application/`, `adapters/`, `bootstrap.py`, `.env.example` nem `mcp/tools.json` no repositório.
- `README.md` está vazio.
- O repositório Git ainda não possui commits.
- `.gitignore` ainda não protege `.env`, embora o `AGENTS.md` determine que ele nunca seja commitado.

Consequência: praticamente toda a aplicação precisa ser criada. Este plano não assume a existência de nenhum componente ainda não implementado.

## 3. Escopo da primeira versão

- API HTTP em FastAPI, stateless, com `POST /agent/messages` e `GET /health`.
- Agente conversacional construído com LangChain 1.x (`create_agent`), orquestrado por uma camada de aplicação independente de frameworks.
- Ferramentas obtidas de um servidor MCP externo via Streamable HTTP (`MCP_SERVER_URL`), sem recriar o servidor, as ferramentas ou o recurso exposto.
- Configuração centralizada com `pydantic-settings`, lendo `.env`.
- Interface web em Streamlit consumindo a API exclusivamente por HTTP com `httpx`.
- Composição de dependências exclusivamente em `bootstrap.py`.
- Sem banco de dados, autenticação, filas, cache externo, observabilidade, checkpointer ou persistência de conversa.
- Sem testes automatizados nesta fase, conforme o `AGENTS.md`.

## 4. Premissas e decisões técnicas de implementação

Estas decisões apenas viabilizam os requisitos do `AGENTS.md`; não substituem nenhuma decisão arquitetural documentada.

1. **Assincronismo nas bordas de I/O.** As portas de aplicação e os adaptadores usarão operações assíncronas onde houver I/O (LLM, MCP, FastAPI), preservando os contratos conceituais do `AGENTS.md` (`run(messages, tools) -> str`, `get_tools`, `is_connected`). Nenhum tipo LangChain/MCP será exposto à camada `application/`.
2. **Ciclo de vida na porta de ferramentas.** Além de `get_tools` e `is_connected`, `ToolProviderPort` exporá `connect` e `close` para que o lifespan da FastAPI não precise conhecer o adaptador MCP concreto. O catálogo de ferramentas será carregado uma única vez no startup.
3. **stdio fora da v1.** O servidor MCP não expõe stdio na fase 1. Portanto, `MCP_SERVER_COMMAND`/`MCP_SERVER_ARGS` não serão implementados nesta versão, embora o `AGENTS.md` os mencione como alternativa canônica.
4. **Recurso MCP fora da v1.** O recurso `dq://...` faz parte do contrato do servidor, mas a arquitetura definida não possui porta, rota ou UI de `resources/read`. Não será implementado sem decisão arquitetural explícita.
5. **`mcp/tools.json` é referência externa.** Se o arquivo não estiver disponível no repositório, os nomes e schemas das ferramentas serão obtidos em runtime via `list_tools()`. O arquivo não deve ser recriado manualmente.
6. **Sem testes automatizados.** As validações serão manuais e por inspeção/importação, conforme a restrição de escopo.

## 5. Tarefas detalhadas

### TASK-001 — Provisionar dependências com `uv`

**Objetivo:** deixar o ambiente com todas as bibliotecas obrigatórias, sem gerenciadores alternativos.

**Descrição:**
- Adicionar com `uv add` (nunca `pip install`): `langchain[mcp]`, `langchain-openai`, `fastapi`, `uvicorn`, `streamlit`, `httpx` e `pydantic-settings`.
- Consultar a documentação oficial vigente do LangChain 1.x antes de fixar versões ou nomes de importação.
- Confirmar a disponibilidade de `create_agent` em `langchain.agents` e de `MCPAdapter` no namespace `langchain.mcp`.
- Não adicionar `langchain-mcp-adapters` nem dependências de teste/lint não previstas.

**Arquivos envolvidos:**
- `pyproject.toml` (modificar)
- `uv.lock` (modificar)

**Dependências:** nenhuma.

**Critérios de aceitação:**
- `uv sync` conclui sem erro.
- `uv run python -c "import fastapi, streamlit, httpx, pydantic_settings, langchain"` funciona.
- `uv run python -c "from langchain.agents import create_agent"` funciona.
- `uv run python -c "from langchain.mcp import MCPAdapter"` funciona; se o namespace oficial divergir, a divergência é registrada antes de prosseguir.
- O `uv.lock` reflete as dependências e não há uso de pip/Poetry/Pipenv/Conda.

**Prioridade:** alta.

---

### TASK-002 — Implementar configuração centralizada

**Objetivo:** centralizar toda configuração e credenciais em `config/settings.py`.

**Descrição:**
- Criar `Settings` com `pydantic-settings`, carregando `.env`.
- Expor os campos canônicos: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `MCP_SERVER_URL`, `API_HOST`, `API_PORT`, `API_BASE_URL`, `OPENAI_API_KEY`, `DISPLAY_QUEST_USER` e `DISPLAY_QUEST_PASSWORD` (esta como `SecretStr`).
- Tratar as chaves de provedor como opcionais individualmente; apenas a chave do provedor selecionado será exigida pela fábrica de LLM.
- Definir valores padrão, quando necessários, exclusivamente neste módulo.
- Disponibilizar uma função de acesso cacheada (por exemplo, `get_settings()`).
- Não implementar `MCP_SERVER_COMMAND`/`MCP_SERVER_ARGS`, pois stdio está fora da fase 1.
- Não colocar URLs, portas, modelos ou chaves em outros módulos.

**Arquivos envolvidos:**
- `src/questai/config/settings.py` (novo)
- `src/questai/config/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-001.

**Critérios de aceitação:**
- A configuração é instanciável a partir de variáveis de ambiente e de `.env`.
- Alterar uma variável de ambiente muda o comportamento sem editar código.
- Os nove campos canônicos estão presentes e tipados corretamente.
- Nenhum outro módulo precisa declarar URL, porta, modelo ou chave.
- A ausência de uma chave não selecionada não impede a inicialização.

**Prioridade:** alta.

---

### TASK-003 — Criar `.env.example` e proteger `.env`

**Objetivo:** documentar a configuração esperada sem expor segredos e impedir o versionamento de `.env`.

**Descrição:**
- Adicionar `.env` ao `.gitignore`, mantendo `.env.example` versionável.
- Criar `.env.example` espelhando exatamente os campos de `Settings`, com valores fictícios ou vazios.
- Usar `http://<host>:8787/mcp` como exemplo de `MCP_SERVER_URL`, conforme o contrato do servidor.
- Não incluir credenciais reais nem variáveis de stdio.

**Arquivos envolvidos:**
- `.gitignore` (modificar)
- `.env.example` (novo)

**Dependências:** TASK-002.

**Critérios de aceitação:**
- Todos os campos de `Settings` aparecem em `.env.example`.
- `.env.example` não contém segredos reais.
- `git check-ignore -v .env` confirma que `.env` está ignorado.
- `.env.example` não é ignorado pelo Git.

**Prioridade:** alta.

---

### TASK-004 — Definir a porta de entrada do agente e os tipos de mensagem

**Objetivo:** estabelecer o contrato da camada de aplicação para receber e responder conversas.

**Descrição:**
- Criar `AgentMessage` com papel (`user` ou `assistant`) e conteúdo textual.
- Criar `AgentReply` com o conteúdo textual da resposta.
- Criar `AgentPort` com `async def handle_message(messages: Sequence[AgentMessage]) -> AgentReply`, que processa o histórico completo.
- Usar apenas `stdlib` e, se necessário, `pydantic`.
- Não importar FastAPI, Streamlit, LangChain, MCP ou adaptadores.
- Documentar que o histórico completo viaja no request e que a aplicação é stateless.

**Arquivos envolvidos:**
- `src/questai/application/ports/inbound/agent_port.py` (novo)
- `src/questai/application/ports/inbound/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-001.

**Critérios de aceitação:**
- `AgentMessage` aceita somente os papéis previstos para o histórico do cliente.
- `AgentPort` não expõe tipos de framework ou de provedor.
- O módulo importa apenas `stdlib`/`pydantic`.
- Não há estado global mutável.

**Prioridade:** alta.

---

### TASK-005 — Definir as portas de saída

**Objetivo:** isolar a aplicação das implementações de LLM e MCP.

**Descrição:**
- Criar `AgentEnginePort` com `run(messages, tools) -> str`, usando `Sequence[object]` para as ferramentas (tipos opacos).
- Criar `ToolProviderPort` com `get_tools() -> Sequence[object]`, `is_connected() -> bool`, `connect()` e `close()`.
- Definir um erro de infraestrutura da aplicação (por exemplo, `ToolProviderError`) para falhas de conexão/transporte/sessão do MCP.
- Garantir que `ToolProviderError` não seja usado para erros de ferramenta reportados pelo MCP (`isError=True`).
- Não importar LangChain, MCP, FastAPI ou Streamlit.
- Documentar que o catálogo de ferramentas é carregado no startup e reutilizado.

**Arquivos envolvidos:**
- `src/questai/application/ports/outbound/llm_port.py` (novo)
- `src/questai/application/ports/outbound/mcp_port.py` (novo)
- `src/questai/application/ports/outbound/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-004.

**Critérios de aceitação:**
- `AgentEnginePort` recebe mensagens e ferramentas opacas, sem tipos LangChain.
- `ToolProviderPort` expõe `get_tools`, `is_connected`, `connect` e `close`.
- Nenhum módulo de `application/` importa frameworks ou SDKs externos.
- A distinção entre falha de transporte e erro de ferramenta está documentada no contrato.

**Prioridade:** alta.

---

### TASK-006 — Implementar o serviço de aplicação

**Objetivo:** orquestrar provedor de ferramentas e motor do agente sem conhecer implementações concretas.

**Descrição:**
- Criar `AgentService` implementando `AgentPort`.
- Receber `ToolProviderPort` e `AgentEnginePort` por injeção no construtor.
- Obter o catálogo de ferramentas via `get_tools()`.
- Encaminhar o histórico completo e as ferramentas para `AgentEnginePort.run(...)`.
- Converter o texto retornado em `AgentReply`.
- Se o provedor estiver desconectado, levantar `ToolProviderError` antes de chamar o motor.
- Não capturar nem transformar erros de ferramenta do MCP.
- Não importar adaptadores concretos nem bibliotecas de framework.

**Arquivos envolvidos:**
- `src/questai/application/services/agent_service.py` (novo)
- `src/questai/application/services/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-004, TASK-005.

**Critérios de aceitação:**
- `AgentService` implementa `AgentPort`.
- O histórico recebido é repassado sem mutação e sem estado entre chamadas.
- O serviço não importa FastAPI, Streamlit, LangChain ou MCP.
- Uma chamada com provedor desconectado resulta em `ToolProviderError`.
- A orquestração não contém lógica específica de provedor de LLM.

**Prioridade:** alta.

---

### TASK-007 — Implementar a fábrica de LLM

**Objetivo:** selecionar provedor e modelo exclusivamente por configuração.

**Descrição:**
- Criar a fábrica que recebe `Settings` e retorna um chat model do LangChain 1.x.
- Usar a API oficial vigente para inicialização de modelos; consultar a documentação antes de codificar.
- Mapear `LLM_PROVIDER` para o provedor suportado (`openai`).
- Aplicar `LLM_MODEL` e `LLM_TEMPERATURE`.
- Ler as chaves somente da configuração/ambiente.
- Falhar com mensagem clara para provedor não suportado ou chave ausente do provedor selecionado.
- Não criar o agente nesta tarefa e não registrar chaves em logs.
- Não espalhar lógica de seleção de provedor para `agent_service.py` ou `routes.py`.

**Arquivos envolvidos:**
- `src/questai/adapters/outbound/llm/llm_factory.py` (novo)
- `src/questai/adapters/outbound/llm/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-001, TASK-002.

**Critérios de aceitação:**
- O modelo/endpoint é definido apenas alterando `LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL`.
- Provedor desconhecido gera erro explícito e compreensível.
- Chave ausente do provedor selecionado gera erro explícito.
- Nenhuma chave é impressa em log ou mensagem de erro.
- A fábrica não cria agente, rota ou serviço.

**Prioridade:** alta.

---

### TASK-008 — Implementar o motor do agente com LangChain 1.x

**Objetivo:** implementar `AgentEnginePort` usando a API vigente `create_agent`.

**Descrição:**
- Criar o adaptador recebendo o chat model já construído pela fábrica.
- Usar `create_agent` de `langchain.agents`; não usar `create_react_agent` nem `AgentExecutor`.
- Converter `AgentMessage` para mensagens do LangChain, preservando papéis e ordem.
- Encaminhar as ferramentas opacas recebidas para o agente.
- Executar o agente e extrair o texto final da resposta do assistente.
- Não adicionar checkpointer, memória persistente ou estado global.
- Não interceptar erros de ferramenta (`isError=True`); eles devem seguir o fluxo normal de correção pelo modelo.
- Não importar implementações concretas de MCP ou componentes de API/UI.

**Arquivos envolvidos:**
- `src/questai/adapters/outbound/agent/langchain_agent_engine.py` (novo)
- `src/questai/adapters/outbound/agent/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-005, TASK-007.

**Critérios de aceitação:**
- O adaptador implementa `AgentEnginePort`.
- `run(...)` retorna o texto final do assistente.
- Históricos com múltiplas mensagens preservam papéis e ordem.
- As ferramentas recebidas são efetivamente disponibilizadas ao agente.
- Chamadas consecutivas são independentes, sem memória residual.
- Não há ocorrência de `create_react_agent` nem `AgentExecutor` no código.
- Erros de ferramenta não são convertidos em exceção pelo adaptador.

**Prioridade:** alta.

---

### TASK-009 — Implementar o adaptador MCP

**Objetivo:** conectar ao servidor MCP externo via Streamable HTTP e expor suas ferramentas como tipos opacos.

**Descrição:**
- Usar a integração oficial `langchain.mcp.MCPAdapter` com `MCP_SERVER_URL`.
- Não usar `MultiServerMCPClient`/`langchain-mcp-adapters`, salvo fallback documentado se o beta oficial quebrar.
- Gerenciar a conexão em `connect()`/`close()`, entrando e saindo do contexto do adaptador.
- No startup, chamar `list_tools()` e manter o catálogo em memória.
- `get_tools()` deve retornar as ferramentas já carregadas, reentrantes, sem reconectar a cada request.
- `is_connected()` deve refletir o estado real do ciclo de vida.
- Garantir que o cliente envie `Content-Type: application/json` e `Accept: application/json, text/event-stream`, conforme o contrato do servidor.
- Enviar as credenciais do DisplayQuest (`DISPLAY_QUEST_USER`/`DISPLAY_QUEST_PASSWORD`) no cabeçalho `Authorization` do transporte e não depender de `Mcp-Session-Id` (servidor stateless).
- Traduzir falhas de conexão/transporte/sessão para `ToolProviderError`; não traduzir erros de ferramenta (`isError=True`).
- Usar `mcp/tools.json`, se disponível, apenas como referência de nomes/argumentos; não recriar ferramentas nem o servidor.
- Não usar `GET`/`DELETE` em `/mcp`; o contrato do servidor aceita somente `POST`.
- Preservar os schemas e as annotations fornecidos pelo servidor; não introduzir convenções próprias de IDs, datas ou meses.
- Não criar `mcp_manager.py`.

**Arquivos envolvidos:**
- `src/questai/adapters/outbound/mcp/mcp_adapter.py` (novo)
- `src/questai/adapters/outbound/mcp/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-001, TASK-002, TASK-005.

**Critérios de aceitação:**
- A conexão é estabelecida com `MCP_SERVER_URL` e o health check externo (`/healthz`) responde quando o servidor está disponível.
- O catálogo carregado corresponde ao contrato do servidor (25 ferramentas, ou divergência reportada de forma explícita).
- `get_tools()` retorna o mesmo conjunto de ferramentas em chamadas sucessivas, sem reconexão por request.
- `close()` encerra o contexto e `is_connected()` passa a refletir o estado desconectado.
- As credenciais do DisplayQuest saem no `Authorization` do transporte; a senha é `SecretStr` e não aparece em log, `repr` ou mensagem de erro. Nenhuma dependência de sessão é introduzida.
- Falha de transporte/conexão vira `ToolProviderError`; erro de ferramenta (`isError=True`) não vira exceção.
- Não há `mcp_manager.py` nem recriação de ferramentas do servidor.

**Prioridade:** alta.

---

### TASK-010 — Definir os schemas HTTP

**Objetivo:** estabelecer o contrato de entrada e saída da API.

**Descrição:**
- Criar `ChatMessage` com papel (`user`/`assistant`) e conteúdo.
- Criar `ChatRequest` contendo a lista completa de mensagens do histórico, com pelo menos uma mensagem.
- Criar `ChatResponse` contendo a resposta textual do assistente.
- Usar `pydantic` e validação declarativa.
- Não expor tipos de LangChain, MCP ou detalhes de provedor.
- Não incluir campos de sessão, usuário autenticado ou persistência.

**Arquivos envolvidos:**
- `src/questai/adapters/inbound/api/schemas.py` (novo)
- `src/questai/adapters/inbound/api/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-004.

**Critérios de aceitação:**
- Payload inválido (papel desconhecido, conteúdo ausente ou lista vazia) resulta em erro de validação `422`.
- Um histórico válido com múltiplas mensagens é aceito.
- O schema de resposta contém apenas a resposta do assistente, sem estado interno.
- Os schemas aparecem corretamente no OpenAPI.
- Nenhum import de backend, LangChain ou MCP.

**Prioridade:** alta.

---

### TASK-011 — Implementar as rotas HTTP

**Objetivo:** expor a conversa e o health check conforme os contratos definidos.

**Descrição:**
- Criar `POST /agent/messages`: converter `ChatRequest` em mensagens da aplicação, chamar o `AgentPort` e devolver `ChatResponse`.
- Criar `GET /health`: informar o estado da API e a conectividade MCP por meio de `ToolProviderPort.is_connected()`.
- Obter serviço e provedor de `app.state` por dependências, sem instanciar adaptadores na rota.
- Não selecionar provedor de LLM, não acessar MCP diretamente e não hardcodar configuração.
- Deixar `ToolProviderError` propagar para o handler da aplicação.
- Manter a API stateless: nenhum histórico é armazenado no servidor.

**Arquivos envolvidos:**
- `src/questai/adapters/inbound/api/routes.py` (novo)

**Dependências:** TASK-006, TASK-010.

**Critérios de aceitação:**
- `POST /agent/messages` responde `200` com o schema de resposta para um histórico válido.
- Payload inválido responde `422`.
- `GET /health` responde `200` com estado da API e conectividade MCP, sem dados sensíveis.
- As rotas aparecem corretamente no OpenAPI.
- Nenhuma rota importa adaptadores concretos ou contém lógica de provedor.
- O histórico utilizado é exclusivamente o enviado no request.

**Prioridade:** alta.

---

### TASK-012 — Implementar app FastAPI, lifespan e tratamento de erros

**Objetivo:** montar a aplicação HTTP com ciclo de vida MCP único e respostas de erro seguras.

**Descrição:**
- Criar `create_app(...)` recebendo as dependências já construídas (`AgentPort` e `ToolProviderPort`), sem instanciar adaptadores concretos.
- Incluir as rotas e armazenar serviço/provedor em `app.state`.
- Implementar lifespan: no startup, conectar o provedor uma única vez e carregar o catálogo; no shutdown, fechar e liberar.
- Definir comportamento explícito para falha de conexão no startup, sem iniciar silenciosamente com catálogo vazio.
- Registrar exception handler para `ToolProviderError`, retornando HTTP `502` com corpo JSON estruturado, sem traceback.
- Não interceptar erros de ferramenta (`isError=True`) no handler.
- Não adicionar checkpointer, banco, cache ou middlewares não previstos.

**Arquivos envolvidos:**
- `src/questai/adapters/inbound/api/app.py` (novo)

**Dependências:** TASK-005, TASK-009, TASK-011.

**Critérios de aceitação:**
- `create_app(...)` retorna uma aplicação FastAPI com as rotas montadas.
- O startup conecta o MCP uma única vez e carrega o catálogo; o shutdown encerra a conexão.
- Falha de conexão inicial é explícita e não gera aplicação operando com catálogo vazio.
- `ToolProviderError` gera `502` com JSON estruturado e sem traceback.
- Erros de ferramenta do MCP não são convertidos em `502` pelo handler.
- `app.py` não importa implementações concretas de LLM/MCP.

**Prioridade:** alta.

---

### TASK-013 — Implementar o bootstrap (composição raiz)

**Objetivo:** compor todas as dependências concretas em um único ponto e expor a fábrica usada pelo Uvicorn.

**Descrição:**
- Criar `bootstrap.py` com `create_app()` compatível com `uvicorn --factory`.
- Carregar `Settings`, construir o chat model com `llm_factory`, o motor LangChain, o adaptador MCP e o `AgentService`.
- Passar serviço e provedor para a fábrica de aplicação.
- Importar a fábrica de `app.py` com alias para evitar colisão com o `create_app` do bootstrap.
- Garantir que `bootstrap.py` seja o único módulo que importa todas as implementações concretas.
- Não duplicar lógica de rotas, serviço, LLM ou MCP.
- Não hardcodar configuração.

**Arquivos envolvidos:**
- `src/questai/bootstrap.py` (novo)

**Dependências:** TASK-007, TASK-008, TASK-009, TASK-012.

**Critérios de aceitação:**
- `uv run uvicorn "questai.bootstrap:create_app" --factory --reload` inicia a API com configuração válida.
- A troca de provedor de LLM ocorre apenas por `LLM_PROVIDER`/`LLM_MODEL`.
- `bootstrap.py` é o único ponto de composição das implementações concretas.
- Nenhuma URL, chave, porta ou modelo está hardcodado fora de `config/settings.py`.
- As rotas e o serviço permanecem independentes de provedor.

**Prioridade:** alta.

---

### TASK-014 — Implementar a interface web em Streamlit

**Objetivo:** oferecer chat multi-turno consumindo a API exclusivamente por HTTP.

**Descrição:**
- Criar a UI com entrada de chat e exibição de mensagens do usuário e do assistente.
- Manter o histórico visual em `st.session_state`.
- A cada envio, chamar `POST {API_BASE_URL}/agent/messages` enviando o histórico completo.
- Exibir indicador de processamento e mensagens de erro amigáveis para falhas HTTP/rede.
- Ler `API_BASE_URL` do ambiente, sem hardcode e sem importar componentes do backend.
- Não importar LangChain, MCP, FastAPI, `application/` ou `adapters/` do projeto.
- Não armazenar histórico no servidor.

**Arquivos envolvidos:**
- `src/questai/adapters/inbound/web/streamlit_app.py` (novo)
- `src/questai/adapters/inbound/web/__init__.py` (novo, se necessário para o pacote)

**Dependências:** TASK-003, TASK-011, TASK-013.

**Critérios de aceitação:**
- `uv run streamlit run src/questai/adapters/inbound/web/streamlit_app.py` abre a interface.
- A conversa mantém contexto entre turnos porque o histórico completo é reenviado.
- A UI usa `httpx` e `API_BASE_URL`; não há URL hardcodada.
- A UI importa apenas `streamlit`, `httpx` e bibliotecas padrão, sem componentes do backend.
- Falhas da API são exibidas de forma amigável, sem traceback cru.
- O histórico existe apenas em `st.session_state`.

**Prioridade:** média.

---

### TASK-015 — Validar a v1 de ponta a ponta

**Objetivo:** confirmar que a aplicação atende aos requisitos funcionais e não funcionais da primeira versão.

**Descrição:**
- Validar manualmente, com o servidor MCP externo disponível e uma chave de LLM configurada:
  - health check do MCP (`/healthz`);
  - startup da API e `GET /health` com MCP conectado;
  - carga do catálogo de ferramentas;
  - conversa com pelo menos uma consulta de leitura que acione uma ferramenta MCP;
  - conversa multi-turno com histórico preservado;
  - cenário de erro de ferramenta (`isError=True`) sem resposta `502`;
  - indisponibilidade do MCP durante uma chamada, resultando em `502` estruturado;
  - interface Streamlit conversando com a API;
  - troca de provedor de LLM apenas por configuração, se houver chaves disponíveis.
- Inspecionar dependências entre camadas e confirmar ausência de imports proibidos.
- Corrigir eventuais falhas encontradas, desde que dentro do escopo definido.
- Não criar arquivos de teste automatizado.

**Arquivos envolvidos:** os arquivos das tarefas anteriores, somente se forem necessários ajustes durante a validação.

**Dependências:** TASK-001 a TASK-014.

**Critérios de aceitação:**
- `GET /health` responde `200` com MCP conectado após o startup.
- O catálogo contém as ferramentas esperadas do servidor (25 no contrato atual) ou a divergência é reportada.
- Uma consulta de leitura usa dados reais do MCP e retorna resposta coerente.
- O segundo turno demonstra que o histórico foi enviado e compreendido.
- Um erro de ferramenta do MCP é tratado como resultado para o modelo, sem `502`.
- Com o MCP indisponível, a API responde `502` com corpo JSON estruturado, sem traceback.
- A UI Streamlit funciona de ponta a ponta via HTTP.
- A troca de provedor de LLM não exige alteração de código em serviço ou rotas.
- Nenhum import proibido existe em `application/`; `domain/` permanece sem entidades.
- `.env` não está versionado e nenhum segredo aparece em logs ou no código.
- Nenhum teste automatizado foi criado.

**Prioridade:** alta.

---

## 6. Dependências entre etapas e tarefas

```text
TASK-001 -> TASK-002, TASK-004
TASK-002 -> TASK-003, TASK-007, TASK-009
TASK-003 -> TASK-014
TASK-004 -> TASK-005, TASK-010
TASK-005 -> TASK-006, TASK-008, TASK-009, TASK-012
TASK-006 -> TASK-011
TASK-007 -> TASK-008, TASK-013
TASK-008 -> TASK-013
TASK-009 -> TASK-012, TASK-013
TASK-010 -> TASK-011
TASK-011 -> TASK-012, TASK-014
TASK-012 -> TASK-013
TASK-013 -> TASK-014, TASK-015
TASK-014 -> TASK-015
TASK-001..TASK-012 -> TASK-015
```

Resumo por etapa:

| Etapa | Tarefas | Depende de | Libera |
|---|---|---|---|
| 1. Preparação | TASK-001, TASK-002, TASK-003 | — | Toda a implementação |
| 2. Núcleo | TASK-004, TASK-005, TASK-006 | Etapa 1 | Adaptadores e API |
| 3. Integrações | TASK-007, TASK-008, TASK-009 | Etapa 1 e TASK-005 | API e composição |
| 4. Entrada HTTP | TASK-010, TASK-011, TASK-012, TASK-013 | Etapas 2 e 3 | Interface web |
| 5. Interface web | TASK-014 | Etapa 4 | Validação final |
| 6. Validação | TASK-015 | Todas as anteriores | Entrega da v1 |

Paralelizações possíveis sem violar dependências:

- TASK-002 e TASK-004 podem avançar em paralelo após TASK-001.
- TASK-007 pode avançar em paralelo ao núcleo (TASK-004 a TASK-006).
- TASK-010 pode avançar em paralelo a TASK-005/TASK-006, pois depende apenas de TASK-004.
- TASK-008 e TASK-009 podem avançar em paralelo depois de suas dependências comuns.

## 7. Critérios gerais para considerar a v1 concluída

1. Todas as tarefas TASK-001 a TASK-015 concluídas e validadas.
2. A API inicia pelo comando do `AGENTS.md` e expõe `POST /agent/messages` e `GET /health`.
3. O agente usa LangChain 1.x com `create_agent`, sem APIs legadas.
4. O MCP é acessado via Streamable HTTP com `MCP_SERVER_URL`, sem recriar servidor ou ferramentas, sem autenticação no cliente e sem dependência de sessão.
5. O catálogo de ferramentas é carregado uma vez no lifespan e reutilizado; ferramentas permanecem chamáveis.
6. A API é stateless e o histórico viaja integralmente do cliente em cada request.
7. Erros de ferramenta do MCP seguem como resultado para o modelo; falhas de transporte retornam `502` estruturado, sem traceback.
8. A troca de provedor/modelo ocorre apenas por configuração, sem alterar serviço ou rotas.
9. A interface Streamlit conversa apenas por HTTP, usando `httpx` e `API_BASE_URL`, com histórico em `st.session_state`.
10. As regras de dependência entre `domain/`, `application/`, `adapters/` e `bootstrap.py` são respeitadas; `domain/` permanece sem entidades.
11. Nenhuma funcionalidade fora do escopo foi adicionada (banco, autenticação, filas, cache externo, observabilidade, checkpointer, multi-servidor ou stdio).
12. `.env` não está versionado, `.env.example` está completo e nenhuma credencial aparece no código ou em logs.
13. Nenhum teste automatizado foi criado nesta fase.
14. Nenhum arquivo do servidor MCP ou de suas ferramentas foi recriado no QuestAI.

## 8. Fora de escopo e pontos de atenção

- **stdio:** não implementar enquanto a fase 1 expuser apenas Streamable HTTP.
- **Recurso `dq://...`:** sem porta/rota/UI prevista no `AGENTS.md`; exige decisão arquitetural antes de qualquer implementação.
- **`mcp/tools.json`:** não está no repositório; usar apenas como referência externa, se fornecido. Não criar manualmente.
- **Beta do `langchain.mcp`:** a API pode divergir da documentação. Validar a assinatura instalada antes de codificar. O fallback `langchain-mcp-adapters` só deve ser usado se o caminho oficial quebrar e com registro da decisão.
- **Disponibilidade do servidor MCP e das chaves de LLM:** necessária para a validação integrada (TASK-015).
- **`API_HOST`/`API_PORT`:** permanecem centralizados em `Settings`; o comando de execução da API continua sendo o documentado no `AGENTS.md`.
- **Sem testes automatizados, lint ou typecheck configurados:** não introduzir ferramentas dessas categorias nesta fase.

## 9. Verificação de consistência do planejamento

- Identificadores únicos: TASK-001 a TASK-015.
- Todas as dependências referenciam tarefas existentes e formam um grafo acíclico.
- A ordem cobre configuração, núcleo, adaptadores, API, UI e validação integrada.
- Não há tarefa de testes automatizados, banco, autenticação ou outras funcionalidades fora do escopo.
- O `AGENTS.md` não é alterado por este planejamento.
- Nenhum caminho de arquivo foi inventado além dos definidos no `AGENTS.md`; arquivos `__init__.py` são indicados apenas quando necessários ao empacotamento.

## 10. Estado de execução e ponto de parada (atualizado em 2026-10-23)

### Status por tarefa

- Etapa 1 (TASK-001 a TASK-003): concluída.
- Etapa 2 (TASK-004 a TASK-006): concluída e verificada (fakes inline: papéis/ordem preservados, `ToolProviderError` em provedor desconectado, papel inválido rejeitado; `application/` importa apenas stdlib/pydantic).
- Etapa 3 (TASK-007 a TASK-009): concluída e verificada (smoke da TASK-008 fechado em 2026-11-03).
  - TASK-007 (`adapters/outbound/llm/llm_factory.py`): validada. `init_chat_model` via `ChatOpenAI` com `LLM_MODEL`/`LLM_TEMPERATURE`/`LLM_BASE_URL`; provedor desconhecido e chave ausente geram `LLMConfigurationError` sem expor chaves.
  - TASK-009 (`adapters/outbound/mcp/mcp_adapter.py` — `MCPToolProvider`): validado contra o servidor real: `connect()` com `MCPAdapter(MCP_SERVER_URL)`, catálogo de 25 ferramentas conforme contrato, `get_tools()` estável sem reconexão, `close()` → `is_connected()=False`, falha de transporte → `ToolProviderError`, erro do servidor (`isError=True`/validação de argumentos) → conteúdo de erro para o modelo, sem exceção. Guard `_guard_transport_errors` preserva `ToolException`/`GraphBubbleUp`/cancelamento.
  - TASK-008 (`adapters/outbound/agent/langchain_agent_engine.py` — `LangChainAgentEngine`): código completo (`create_agent` de `langchain.agents`, conversão de papéis/ordem, sem checkpointer, sem `create_react_agent`/`AgentExecutor`). Smoke end-to-end concluído em 2026-11-03 (AgentService + motor + MCP real + LLM configurado): `project_list` acionada com dado real ("14 projetos"), turno 2 preservou o contexto via histórico completo, chamada independente sem memória residual, `project_get(999999)` → `not_found` reportado pelo modelo sem exceção/`502` (`isError=True` flui ao modelo), `close()` → `is_connected=False`. Latências 3–9s.

### Motivo da parada — RESOLVIDO (2026-11-03)

- O bloqueio era a ausência das credenciais DisplayQuest no `.env` (o MCP aguardava autenticação). Mecanismo confirmado e registrado no `AGENTS.md` (`Authorization: Basic` com `DISPLAY_QUEST_USER`/`DISPLAY_QUEST_PASSWORD` no transporte).
- TASK-002 (campos em `settings.py`, senha `SecretStr`, espelho em `.env.example`) e TASK-009 (`_authenticated_target` no `MCPToolProvider`) ajustadas. Smoke reexecutado sem hangs.

### Arquivos criados até aqui

```text
src/questai/domain/                                    (vazio, como exigido)
src/questai/application/ports/inbound/agent_port.py
src/questai/application/ports/outbound/llm_port.py
src/questai/application/ports/outbound/mcp_port.py
src/questai/application/services/agent_service.py
src/questai/adapters/outbound/llm/llm_factory.py
src/questai/adapters/outbound/agent/langchain_agent_engine.py
src/questai/adapters/outbound/mcp/mcp_adapter.py
(+ __init__.py dos pacotes correspondentes)
```

### Etapa 4 (TASK-010 a TASK-013): concluída e verificada (2026-10-28)

- TASK-010 (`adapters/inbound/api/schemas.py`): `ChatMessage` (papéis `user`/`assistant`), `ChatRequest` (histórico com pelo menos uma mensagem), `ChatResponse` (apenas a resposta textual). Validação declarativa; payload inválido (lista vazia, papel desconhecido, conteúdo ausente) → `422`; schemas presentes no OpenAPI; sem imports de backend.
- TASK-011 (`adapters/inbound/api/routes.py`): `POST /agent/messages` converte `ChatRequest` em `AgentMessage` e chama o `AgentPort`; `GET /health` reporta `status` e `mcp_connected` via `ToolProviderPort.is_connected()`. Serviço e provedor obtidos de `app.state` via Depends; rotas importam apenas portas de aplicação, sem provedor/lógica concreta. Histórico multi-turno repassado integralmente (papéis e ordem preservados, verificado com fake).
- TASK-012 (`adapters/inbound/api/app.py`): `create_app(agent_service, tool_provider)` recebe contratos, não implementações. Lifespans: startup conecta e carrega o catálogo uma única vez; shutdown encerra. Falha de conexão no startup aborta o boot (aplicação não sobe com catálogo vazio). Handler de `ToolProviderError` → `502` com corpo JSON estruturado, sem traceback. Erros de ferramenta (`isError=True`) não passam pelo handler.
- TASK-013 (`bootstrap.py`): composição raiz, único módulo que conhece as implementações concretas; `create_app()` compatível com `uvicorn --factory` (importado `create_app as build_api_app` para evitar colisão). Startup real validado: `uv run uvicorn "questai.bootstrap:create_app" --factory` subiu com MCP conectado (`GET /health` → `{"status":"ok","mcp_connected":true}`) e shutdown limpo.

Arquivos criados na Etapa 4:

```text
src/questai/adapters/inbound/api/__init__.py
src/questai/adapters/inbound/api/schemas.py
src/questai/adapters/inbound/api/routes.py
src/questai/adapters/inbound/api/app.py
src/questai/adapters/inbound/__init__.py
src/questai/bootstrap.py
```

### Etapa 5 (TASK-014): concluída e verificada (2026-11-03)

- `adapters/inbound/web/streamlit_app.py` + `__init__.py`: chat com `st.chat_message`/`st.chat_input`, histórico completo em `st.session_state`, `st.spinner` no envio, erros amigáveis para HTTP/rede (sem traceback), erros não entram no histórico. `API_BASE_URL` lida exclusivamente do ambiente (fallback `API_HOST`/`API_PORT`); imports apenas `os`, `httpx`, `streamlit` (verificado por AST).
- Verificado: app sobe headless (`streamlit run`, porta 8501); sem env exibe mensagem amigável; caminho de erro HTTP (timeout) exibe `st.error` sem exceção; POST direto à API respondeu `200` com dado real do MCP ("14 projetos").
- Verificado em 2026-11-03 (AppTest com API real via `uvicorn "questai.bootstrap:create_app" --factory`, MCP conectado): turno 1 pela UI acionou ferramenta MCP e respondeu com dado real ("14 projetos"); turno 2 respondeu com o contexto do turno 1 ("Eu disse **14 projetos**") porque o histórico completo foi reenviado; ordem de papéis `user, assistant, user, assistant` em `st.session_state`; zero `st.error`; sem traceback.
- Pendente: nenhum. Etapa 6 (TASK-015) permanece pendente.

### Etapa 6 (TASK-015): concluída e verificada (2026-11-03)

Validação integrada de ponta a ponta, manual (sem testes automatizados no repo), com servidor MCP real e LLM OpenAI-compatible configurado:

- Health do MCP externo (`/healthz`) → `ok`; `GET /health` da API → `{"status":"ok","mcp_connected":true}`; catálogo carregado no startup com as 25 ferramentas do contrato.
- Consulta de leitura via API: `project_list` acionada, resposta com dado real ("14 projetos"). Multi-turno com histórico completo reenviado: segundo turno respondeu com o contexto do primeiro. UI Streamlit validada de ponta a ponta (AppTest, dois turnos, histórico só em `st.session_state`, zero `st.error`).
- Erro de ferramenta (`project_get` com `projectId=999999`): `not_found` reportado pelo modelo, HTTP `200`, sem `502`. Payloads inválidos (lista vazia, papel desconhecido, conteúdo ausente) → `422`.
- MCP indisponível durante chamada (servidor mock local morto em meio à sessão): `502` com corpo JSON estruturado `{"error":{"type":"tool_provider_error","message":...}}`, sem traceback.
- Startup com MCP inalcançável: aborta explicitamente (`Application startup failed. Exiting.`), a aplicação não sobe com catálogo vazio.
- Ajuste encontrado na validação (dentro do escopo da TASK-012): no shutdown, `close()` com MCP já morto levantava `ToolProviderError` no lifespan e o uvicorn registrava `Application shutdown failed` com traceback cru. O lifespan agora tolera essa falha com `logger.warning` e shutdown limpo; o contrato da porta (`close()` → `ToolProviderError`) foi preservado.
- Troca de provedor/modelo apenas por configuração: `LLM_MODEL=qwen3.8-flash-next` → API respondeu sem alterar código; `LLM_PROVIDER=anthropic` → `LLMConfigurationError` explícito; `OPENAI_API_KEY` ausente → erro explícito sem expor chave.
- Imports por AST: `application/` importa apenas stdlib/pydantic; `routes.py`/`app.py` importam apenas portas + schemas; `streamlit_app.py` importa apenas `os`/`httpx`/`streamlit`; `bootstrap.py` é o único ponto de composição; `domain/` permanece vazio.
- `.env` ignorado pelo Git (`git check-ignore`), `.env.example` espelha todos os campos de `Settings` sem segredos; nenhum segredo em código/logs; nenhum teste automatizado criado; nenhum arquivo do servidor MCP recriado.

### Adição pós-validação: system prompt do agente (2026-11-03)

- `adapters/outbound/agent/langchain_agent_engine.py`: constante `SYSTEM_PROMPT` (identidade QuestAI, papel de assistente do laboratório via ferramentas DisplayQuest, respostas em pt-BR, uso de dados reais sem inventar IDs/valores, confirmação antes de ferramentas de escrita, reporte fiel de erros de ferramenta) aplicada via `system_prompt` do `create_agent`. Escopo da TASK-008, sem mudança de portas/serviço/rotas.
- Validado: agente declara identidade ("Sou o QuestAI..."), aciona ferramentas sem ser instruído (consulta livre de projetos → `project_list` → "14 projetos") e multi-turno preservado.

### Estado final da v1

- Etapas 1 a 6 concluídas. Pendências: nenhuma para a v1.
- Próximos passos fora do escopo da v1 (exigem decisão própria): commits do repo, testes automatizados, recurso `dq://` (DOCX), stdio, autenticação de cliente no MCP.
