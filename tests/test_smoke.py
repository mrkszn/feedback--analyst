"""Sanity-тесты, без сетевых вызовов.

Запускаются на каждом pytest-прогоне и на pre-commit. Цель — поймать
дрейф зависимостей и сломанный config-loader до того, как фича-команды
наткнутся на них.
"""


def test_config_loads():
    from config import settings

    assert settings.env in {"local", "staging", "prod"}
    assert settings.openai_chat_model
    assert settings.pinecone_index
    assert settings.pinecone_namespace


def test_key_imports():
    """Catches dep drift early."""
    import aiogram  # noqa: F401
    import fastapi  # noqa: F401
    import langchain_openai  # noqa: F401
    import langchain_pinecone  # noqa: F401
    import langgraph  # noqa: F401
    import openai  # noqa: F401
    import pinecone  # noqa: F401
    import structlog  # noqa: F401
    import supabase  # noqa: F401


def test_langgraph_state_graph_api():
    """LangGraph API стабильность: импорт StateGraph + START/END.

    Если LangGraph выпустит мажорку с переименованием, тест упадёт
    раньше, чем мы начнём чинить графы.
    """
    from langgraph.graph import END, START, StateGraph

    assert StateGraph is not None
    assert START is not None
    assert END is not None
