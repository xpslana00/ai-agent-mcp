"""ReAct agent (LangChain 1.x / LangGraph) s nastroji z MCP serveru a LLM Gemini.

Spusteni:  python agent.py
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver

from init_db import DB_PATH, create_db

BASE_DIR = Path(__file__).parent

SYSTEM_PROMPT = """Jsi IT asistent. Odpovidej cesky, strucne a vecne.
Mas k dispozici nastroje:
- wikipedia_search: obecne a encyklopedicke informace,
- db_schema + sql_query: databaze IT majetku (uzivatele a zarizeni) - nejdriv zjisti schema,
- calculator: kazdy vypocet,
- web_search (pokud je k dispozici): aktualni informace z internetu.
Postupuj ve smycce Uvaha -> Akce (nastroj) -> Pozorovani, dokud nemas odpoved.
Nevymyslej si data; kdyz je nastroj nenajde, rekni to. U Wikipedie/webu uved zdroj."""


def text_of(message) -> str:
    """Vrati text zpravy (Gemini muze vracet content jako seznam bloku)."""
    content = message.content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


async def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        sys.exit("Chybi GOOGLE_API_KEY v souboru .env (viz .env.example).")
    if not DB_PATH.exists():
        create_db()

    # 1) Pripojeni k MCP serveru a nacteni nastroju
    client = MultiServerMCPClient({
        "agent-tools": {
            "command": sys.executable,
            "args": [str(BASE_DIR / "mcp_server.py")],
            "transport": "stdio",
        }
    })
    tools = await client.get_tools()
    print("Nactene MCP nastroje:", ", ".join(t.name for t in tools))

    # 2) LLM + ReAct agent s pameti konverzace
    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"), timeout=60, max_retries=2
    )
    agent = create_agent(
        model, tools, system_prompt=SYSTEM_PROMPT, checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "cli-session"}}

    # 3) Interaktivni smycka
    print("Agent je pripraven. Napis dotaz (nebo 'konec').\n")
    seen = 0
    while True:
        question = input("Ty: ").strip()
        if question.lower() in {"konec", "exit", "quit"}:
            break
        if not question:
            continue
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]}, config
        )
        messages = result["messages"]
        for m in messages[seen:]:  # vypis prubehu ReAct smycky
            for call in getattr(m, "tool_calls", None) or []:
                print(f"  [akce] {call['name']}({call['args']})")
            if m.type == "tool":
                preview = text_of(m).replace("\n", " ")[:150]
                print(f"  [pozorovani] {preview}...")
        seen = len(messages)
        print(f"\nAgent: {text_of(messages[-1])}\n")


if __name__ == "__main__":
    asyncio.run(main())
