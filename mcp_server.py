"""MCP server s nastroji (tooly) pro agenta.

Spousti se automaticky z agent.py pres stdio transport,
lze ho ale pouzit i z jineho MCP klienta (napr. MCP Inspector, VS Code).
"""
import ast
import operator
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "it_assets.db"
load_dotenv(BASE_DIR / ".env")

mcp = FastMCP("agent-tools")
HTTP_HEADERS = {"User-Agent": "ai-agent-mcp-ukol/1.0 (skoleni AI agenti)"}


# ---------------------------------------------------------------- Wikipedia
@mcp.tool()
def wikipedia_search(query: str, lang: str = "cs") -> str:
    """Vyhleda tema na Wikipedii a vrati kratke shrnuti nejrelevantnejsiho clanku.

    Args:
        query: hledany vyraz
        lang: jazyk Wikipedie, napr. 'cs' nebo 'en'
    """
    try:
        with httpx.Client(timeout=15, headers=HTTP_HEADERS) as client:
            r = client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": query,
                        "srlimit": 1, "format": "json"},
            )
            hits = r.json()["query"]["search"]
            if not hits:
                return f"Na Wikipedii ({lang}) nebylo nic nalezeno pro: {query}"
            title = hits[0]["title"]
            s = client.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                f"{quote(title.replace(' ', '_'))}"
            )
            data = s.json()
            url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            return f"{data.get('title', title)}: {data.get('extract', '')}\nZdroj: {url}"
    except Exception as e:  # chybu vratime modelu, at muze reagovat
        return f"Chyba pri dotazu na Wikipedii: {e}"


# ---------------------------------------------------------------- SQL databaze
@mcp.tool()
def db_schema() -> str:
    """Vrati seznam tabulek a sloupcu v SQLite databazi IT majetku.
    Zavolej VZDY pred psanim SQL dotazu."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return "\n\n".join(f"-- {name}\n{sql}" for name, sql in rows)
    finally:
        conn.close()


@mcp.tool()
def sql_query(query: str) -> str:
    """Spusti READ-ONLY SQL dotaz (pouze SELECT) nad databazi IT majetku
    (tabulky users a devices) a vrati vysledek jako tabulku (max. 50 radku)."""
    q = query.strip().rstrip(";")
    if not q.lower().startswith(("select", "with")) or ";" in q:
        return "Chyba: povolen je pouze jeden dotaz typu SELECT."
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)  # read-only
    try:
        cur = conn.execute(q)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchmany(50)
        if not rows:
            return "Dotaz nevratil zadne radky."
        lines = [" | ".join(cols)] + [" | ".join(str(v) for v in row) for row in rows]
        return "\n".join(lines)
    except sqlite3.Error as e:
        return f"SQL chyba: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------- Kalkulacka
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Nepodporovany vyraz")


@mcp.tool()
def calculator(expression: str) -> str:
    """Bezpecne spocita matematicky vyraz, napr. '(1250 * 21) / 100' nebo '2**10'.
    Pouzij pro kazdy vypocet misto pocitani z hlavy."""
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"Chyba vypoctu: {e}"


# ---------------------------------------------------------------- Tavily (volitelne)
if os.getenv("TAVILY_API_KEY"):

    @mcp.tool()
    def web_search(query: str) -> str:
        """Vyhleda aktualni informace na internetu (Tavily). Pouzij pro aktualni
        udalosti, ceny, verze produktu apod."""
        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
                json={"query": query, "max_results": 3},
                timeout=20,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            return "\n\n".join(
                f"{x['title']}\n{x['url']}\n{x.get('content', '')[:500]}" for x in results
            ) or "Nic nenalezeno."
        except Exception as e:
            return f"Chyba pri vyhledavani: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
