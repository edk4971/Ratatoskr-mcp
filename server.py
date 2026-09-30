import os

from mcp.server.mcpserver import MCPServer
from retrieval import fetch_page_content

mcp = MCPServer("Wikipedia")

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
    transport = os.environ.get("MCP_TRANSPORT", "sse").lower()
    # Normalise legacy names
    if transport == "http":
        transport = "streamable-http"
    # Validate
    if transport not in ("stdio", "sse", "streamable-http"):
        transport = "sse"
    mcp.run(transport=transport, host=host, port=port)
