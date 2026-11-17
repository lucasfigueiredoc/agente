# QuestAI — chat integrado ao DisplayQuest

O painel QuestAI usa a sessão já autenticada no DisplayQuest. A API Python exige
`Authorization: Bearer <QUESTAI_INTEGRATION_TOKEN>` e `X-DisplayQuest-Session`.
Esses headers são montados pelo backend do DisplayQuest; não são pedidos ao usuário
nem entregues ao modelo. O MCP precisa estar atualizado para o modo de sessão.

## Configuração local

- Configure o mesmo segredo aleatório (mínimo 32 caracteres) em
  `QUESTAI_INTEGRATION_TOKEN` nos ambientes do DisplayQuest, MCP e QuestAI.
- Configure `MCP_SERVER_URL` com o MCP local. Preserve a configuração do modelo.
- No DisplayQuest, `QUESTAI_API_URL=http://host.docker.internal:8000` quando o app
  roda em Docker e o Python no host Windows.
- Instale com `uv sync` e execute:

```powershell
uv run python -m uvicorn "questai.bootstrap:create_app" --factory --host 0.0.0.0 --port 8000
```

O bind em todas as interfaces permite o acesso pelo Docker. A rota de chat exige
o segredo e a sessão. Em implantação fora da máquina local, use HTTPS entre
serviços e limite a rede à infraestrutura da aplicação.

No DisplayQuest, reconstrua `app` e `mcp` com Docker Compose e abra o botão QuestAI
após o login. O histórico vive somente na memória do navegador e é enviado a cada
pergunta, sem persistência. O Streamlit anterior não envia sessão e não funciona
com a API protegida. `/health` informa o modo `user_session`, sem sondagem global MCP.

`GET /ready`, autenticado com os mesmos headers do chat, retorna `available`.
Verifica em paralelo a abertura do catálogo MCP com a sessão do usuário e a
presença do modelo configurado em `/models` no endpoint OpenAI-compatible.
Tem limite de 4 segundos, não gera texto e não executa ferramentas de dados.
O DisplayQuest usa essa sondagem para desabilitar o botão quando necessário.

## Autorização

Um cliente MCP separado é criado por requisição e liberado ao final. Não existe
fallback para a conta de serviço. O MCP valida a sessão e chama as APIs existentes
com seus cookies; permissões, vínculos e visibilidade continuam no DisplayQuest.
As permissões existentes podem permitir leitura ampla de projetos e horas a
usuários autenticados. Esta integração não restringe nem amplia essas regras.

As ferramentas de escrita existentes continuam sujeitas às permissões do usuário.
A confirmação conversacional solicitada pelo prompt não é um mecanismo de
aprovação transacional. Nenhuma escrita é necessária para validar a integração.
