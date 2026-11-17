import os

import httpx
import streamlit as st

REQUEST_TIMEOUT_SECONDS = 300.0


def api_base_url() -> str | None:
    """Base URL da API exclusivamente pelo ambiente, sem hardcode."""
    base = os.environ.get("API_BASE_URL")
    if base:
        return base
    host = os.environ.get("API_HOST")
    port = os.environ.get("API_PORT")
    if host and port:
        return f"http://{host}:{port}"
    return None


if "messages" not in st.session_state:
    st.session_state["messages"] = []

st.title("QuestAI")

base = api_base_url()
if not base:
    st.error("Defina API_BASE_URL (ou API_HOST/API_PORT) no ambiente para conversar.")
    st.stop()

for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def call_api(history: list[dict[str, str]]) -> tuple[str, str | None]:
    """Envie o histórico completo à API; retorna (resposta, erro_amigável).

    Falhas de rede/HTTP viram texto amigável; nenhum traceback cru é exibido.
    """
    try:
        response = httpx.post(
            f"{base}/agent/messages",
            json={"messages": history},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            error = exc.response.json().get("error", {})
        except ValueError:
            error = {}
        return "", f"API respondeu {exc.response.status_code}: {error.get('message', 'falha na API')}"
    except httpx.RequestError as exc:
        return "", f"Falha de comunicação com a API: {exc}"

    return response.json()["content"], None


if prompt := st.chat_input("Mensagem"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processando..."):
            reply, error = call_api(st.session_state["messages"])
        if error:
            st.error(error)
        else:
            st.markdown(reply)
            st.session_state["messages"].append({"role": "assistant", "content": reply})
