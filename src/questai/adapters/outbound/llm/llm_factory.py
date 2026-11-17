from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from questai.config.settings import Settings

SUPPORTED_PROVIDERS = ("openai",)


class LLMConfigurationError(ValueError):
    """Erro de configuração do provedor de LLM (provedor desconhecido ou chave ausente)."""


def build_chat_model(settings: Settings) -> BaseChatModel:
    """Seleciona e instancia o chat model do LangChain apenas por configuração.

    Lê `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_BASE_URL` e a chave
    do provedor selecionado exclusivamente de `Settings`. Nunca cria agente,
    rota ou serviço e nunca inclui chaves em mensagens de erro.
    """
    provider = settings.llm_provider.strip().lower()

    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMConfigurationError(
                "A chave OPENAI_API_KEY é obrigatória quando LLM_PROVIDER=openai."
            )
        kwargs: dict[str, object] = {
            "api_key": settings.openai_api_key,
            "temperature": settings.llm_temperature,
        }
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        return init_chat_model(
            settings.llm_model,
            model_provider="openai",
            **kwargs,
        )

    raise LLMConfigurationError(
        f"Provedor de LLM não suportado: {provider!r}. "
        f"Provedores suportados: {', '.join(SUPPORTED_PROVIDERS)}."
    )
