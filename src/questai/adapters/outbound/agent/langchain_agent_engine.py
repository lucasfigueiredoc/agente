from collections.abc import Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from questai.application.ports.inbound.agent_port import AgentMessage
from questai.application.ports.outbound.llm_port import AgentEnginePort

SYSTEM_PROMPT = """Você é o QuestAI, um agente de IA que auxilia no gerenciamento de projetos e \
atividades de um laboratório acadêmico universitário. Você acessa o sistema Display Quest por meio \
de ferramentas MCP fornecidas em cada execução.

Regras:
- Responda sempre em português do Brasil.
- Use as ferramentas para obter dados reais; nunca invente projetos, membros, tarefas, IDs, datas ou números.
- Prefira ferramentas de leitura para consultar dados; em ferramentas de escrita (criar/atualizar/generar), \
confirme com o usuário antes de executar e informe exatamente o que foi criado.
- Se uma ferramenta retornar erro, reporte a mensagem de erro com fidelidade e proponha um caminho para \
corrigir os argumentos; não tente adivinar dados que a ferramenta não devolveu.
- Cite IDs e valores retornados pelas ferramentas quando forem relevantes para a resposta.
- Responda à pergunta com um resumo objetivo, em linguagem de gestão. Não transforme uma consulta
  simples em uma ficha de todos os campos do banco. Em listagens de projetos, apresente nome,
  situação e, se útil, responsável; acrescente outros dados apenas quando solicitados ou relevantes.
- Traduza valores técnicos: active = ativo, pending = pendente. Não mostre nomes de campos,
  nomes de ferramentas MCP, JSON, null, IDs internos ou e-mails sem necessidade explícita.
  Para algo importante que não esteja preenchido, diga "não informado". Ignore espaços nas
  extremidades dos nomes ao exibi-los, sem sugerir que o cadastro foi alterado.
- Ausência de um campo no resultado NÃO comprova ausência de dados: uma listagem sem entregáveis
  não permite afirmar que o projeto não tem entregáveis. Consulte o detalhe apropriado antes
  de concluir isso; quando não puder verificar, diga que a informação não foi consultada.
- Use parágrafos curtos e listas simples. Use tabelas apenas para comparar vários registros ou
  quando o usuário pedir. Evite tabelas verticais de campo/valor em respostas comuns.
- Não ofereça "executar project_get" ou outros detalhes técnicos. Se sugerir um próximo passo,
  descreva a finalidade, como "Posso consultar as tarefas e as horas deste projeto".
- Exemplo de estilo para uma listagem com um único projeto: "Há 1 projeto cadastrado: **Teste**,
  ativo, com Lucas na gestão do projeto." Use apenas fatos realmente retornados pelas ferramentas.
- Você não tem memória entre requisições: o histórico da conversa chega completo em cada mensagem.
"""


def _to_langchain_messages(messages: Sequence[AgentMessage]) -> list[AnyMessage]:
    converted: list[AnyMessage] = []
    for message in messages:
        if message.role == "user":
            converted.append(HumanMessage(content=message.content))
        else:
            converted.append(AIMessage(content=message.content))
    return converted


def _final_text(messages: Sequence[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            content = message.content
            if isinstance(content, str):
                return content
            parts = [
                block["text"]
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            return "\n".join(parts)
    return ""


class LangChainAgentEngine(AgentEnginePort):
    """Motor do agente via `create_agent` (LangChain 1.x).

    Stateless: constrói o agente a cada execução, sem checkpointer, memória
    persistente ou estado global. As ferramentas recebidas são opacas para a
    camada de aplicação, mas aqui são as `BaseTool` produzidas pelo adaptador
    MCP. Erros de ferramenta reportados pelo provedor (`isError=True`) já são
    convertidos em `ToolMessage(status="error")` pela própria integração oficial
    e seguem o fluxo normal de autocorreção do modelo — não são interceptados.
    """

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def run(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[object],
    ) -> str:
        agent = create_agent(self._model, tools=list(tools), system_prompt=SYSTEM_PROMPT)
        result = await agent.ainvoke({"messages": _to_langchain_messages(messages)})
        return _final_text(result["messages"])
