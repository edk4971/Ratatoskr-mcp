import os

from fastmcp import FastMCP
from retrieval import fetch_page_content

mcp = FastMCP("Wikipedia")

@mcp.tool()
def get_wikipedia_article(topic: str) -> str:
    """
    Retrieves the content of a Wikipedia article by its title.

    Args:
        topic: The title of the Wikipedia article.

    Returns:
        The article content in Markdown format, or an error message if not found.
    """
    content = fetch_page_content(topic)
    if content:
        return content
    else:
        return f"Could not find Wikipedia article: {topic}"

if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport="sse", host=host, port=port)
