#!/usr/bin/env python3
import os
import sys
import json
import asyncio
from typing import Any, Dict, List, Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    from notion_client import Client
except ImportError:
    print("Error: Missing dependencies. Install with: pip install mcp notion-client", file=sys.stderr)
    sys.exit(1)


class NotionMCPServer:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("NOTION_TOKEN", "")
        if not self.token:
            print("Warning: NOTION_TOKEN not set. Some features may not work.", file=sys.stderr)
        self.notion = Client(auth=self.token) if self.token else None
        self.server = Server("notion-mcp-server")

    def setup_tools(self):
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="notion_search",
                    description="Search Notion pages and databases",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="notion_list_pages",
                    description="List Notion pages",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "number",
                                "description": "Maximum number of pages to return",
                                "default": 10
                            }
                        }
                    }
                ),
                Tool(
                    name="notion_get_page",
                    description="Get a specific Notion page by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "Notion page ID"
                            }
                        },
                        "required": ["page_id"]
                    }
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            if not self.notion:
                return [TextContent(
                    type="text",
                    text="Error: Notion client not initialized. Set NOTION_TOKEN environment variable."
                )]

            if name == "notion_search":
                query = arguments.get("query", "")
                try:
                    results = self.notion.search(query=query)
                    items = []
                    for item in results.get("results", [])[:10]:
                        title = "Untitled"
                        if "properties" in item:
                            props = item["properties"]
                            for prop_name, prop_value in props.items():
                                if prop_value.get("type") == "title" and prop_value.get("title"):
                                    title = "".join([t.get("plain_text", "") for t in prop_value["title"]])
                                    break
                        elif "title" in item:
                            if isinstance(item["title"], list):
                                title = "".join([t.get("plain_text", "") for t in item["title"]])
                            else:
                                title = str(item["title"])
                        
                        items.append({
                            "id": item.get("id", ""),
                            "title": title,
                            "url": item.get("url", ""),
                            "type": item.get("object", ""),
                            "last_edited": item.get("last_edited_time", "")
                        })
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({"items": items}, indent=2)
                    )]
                except Exception as e:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": str(e)})
                    )]

            elif name == "notion_list_pages":
                limit = arguments.get("limit", 10)
                try:
                    results = self.notion.search(filter={"property": "object", "value": "page"}, page_size=limit)
                    items = []
                    for item in results.get("results", []):
                        title = "Untitled"
                        if "properties" in item:
                            props = item["properties"]
                            for prop_name, prop_value in props.items():
                                if prop_value.get("type") == "title" and prop_value.get("title"):
                                    title = "".join([t.get("plain_text", "") for t in prop_value["title"]])
                                    break
                        
                        items.append({
                            "id": item.get("id", ""),
                            "title": title,
                            "url": item.get("url", ""),
                            "last_edited": item.get("last_edited_time", "")
                        })
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({"items": items}, indent=2)
                    )]
                except Exception as e:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": str(e)})
                    )]

            elif name == "notion_get_page":
                page_id = arguments.get("page_id", "")
                try:
                    page = self.notion.pages.retrieve(page_id=page_id)
                    blocks = self.notion.blocks.children.list(block_id=page_id)
                    
                    content = []
                    for block in blocks.get("results", []):
                        block_type = block.get("type", "")
                        if block_type == "paragraph":
                            para = block.get("paragraph", {})
                            if "rich_text" in para:
                                text = "".join([t.get("plain_text", "") for t in para["rich_text"]])
                                content.append(text)
                        
                        # Extract text from other block types as needed
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "id": page.get("id", ""),
                            "title": page.get("properties", {}).get("title", {}),
                            "url": page.get("url", ""),
                            "content": "\n".join(content)
                        }, indent=2)
                    )]
                except Exception as e:
                    return [TextContent(
                        type="text",
                        text=json.dumps({"error": str(e)})
                    )]

            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]

    async def run(self):
        self.setup_tools()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    token = None
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--token"):
                token = arg.split("=", 1)[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]
                break
    
    server = NotionMCPServer(token=token)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()



