from __future__ import annotations

import anyio
import logging
from typing import Any, Dict
from .mcp_client import MCPHarness
from .reasoning import correlate, parse_query

logger = logging.getLogger("agent")


class AgentService:
    def __init__(self) -> None:
        self.harness = MCPHarness()

    def check_connectivity(self) -> Dict[str, Any]:
        async def run():
            from django.conf import settings
            
            notion_configured = bool(settings.NOTION_MCP_CMD)
            git_configured = bool(settings.GIT_MCP_CMD)
            
            details = {
                "notion_configured": notion_configured,
                "git_configured": git_configured,
                "notion_cmd": settings.NOTION_MCP_CMD if notion_configured else "Not configured",
                "git_cmd": settings.GIT_MCP_CMD if git_configured else "Not configured",
            }
            
            if not notion_configured and not git_configured:
                return {
                    "ok": False,
                    "details": {
                        **details,
                        "message": "No MCP servers configured. Set NOTION_MCP_CMD and/or GIT_MCP_CMD in .env",
                    },
                }
            
            notion_items = []
            git_items = []
            errors = []
            
            if notion_configured:
                try:
                    notion_items = await self.harness.notion_list()
                    details["notion_items"] = len(notion_items)
                    details["notion_available_tools"] = [item.get("name") for item in notion_items[:5]]
                except Exception as e:
                    errors.append(f"Notion: {str(e)}")
                    details["notion_error"] = str(e)
            
            if git_configured:
                try:
                    git_tools = await self.harness.git_list()
                    details["git_available_tools"] = [tool.get("name") for tool in git_tools[:10]]
                    git_items = await self.harness.git_search("test")
                    details["git_results"] = len(git_items)
                except Exception as e:
                    errors.append(f"Git: {str(e)}")
                    details["git_error"] = str(e)
            
            return {
                "ok": len(errors) == 0,
                "details": {
                    **details,
                    "errors": errors if errors else None,
                },
            }

        try:
            return anyio.run(run)
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "details": {"error": str(exc)}}

    def handle_query(self, query: str, scenario: str = "generic") -> Dict[str, Any]:
        async def run():
            logger.info(f"=== Starting query: {query} ===")
            
            logger.info("Parsing query with NLP...")
            parsed = parse_query(query)
            notion_query = parsed.get("notion_query", query)
            git_query = parsed.get("git_query", query)
            query_type = parsed.get("query_type", "general")
            is_my_query = parsed.get("is_my_query", False)
            intent = parsed.get("intent", "General search")
            
            if git_query:
                original_git_query = git_query
                git_query = git_query.replace("{username}", "").replace("{repo_name}", "").replace("user:", "").replace("repo:", "").strip()
                if query_type == "commit" and not git_query.strip():
                    keywords = parsed.get("keywords", [])
                    git_query = " ".join(keywords) if keywords else query
                else:
                    cleaned = git_query.replace("list_commits", "").replace("search_code", "").replace("search_repositories", "").strip()
                    git_query = cleaned if cleaned else git_query
            
            # If git_query is empty after cleanup, use original query
            if not git_query:
                git_query = query
            
            logger.info(f"Parsed query - Type: {query_type}, Intent: {intent}")
            logger.info(f"Notion query: {notion_query}")
            logger.info(f"Git query: {git_query}")
            
            logger.info("Querying Notion MCP server...")
            notion = await self.harness.notion_query(notion_query)
            logger.info(f"Notion returned {len(notion)} items")
            
            logger.info("Querying Git MCP server...")
            git = await self.harness.git_search(git_query, query_type=query_type, is_my_query=is_my_query, is_count_query=any(word in query.lower() for word in ["how many", "count", "number of"]))
            logger.info(f"Git returned {len(git)} items")
            
            logger.info("Correlating results with OpenAI...")
            combined = correlate(notion, git, query)
            logger.info(f"Correlation result: summary length={len(combined.get('summary', ''))}, citations={len(combined.get('citations', []))}")
            
            result = {
                "scenario": scenario,
                "query": query,
                "summary": combined.get("summary", ""),
                "citations": combined.get("citations", []),
                "debug": {
                    "notion_items_count": len(notion),
                    "git_items_count": len(git),
                    "notion_sample": notion[:2] if notion else [],
                    "git_sample": git[:2] if git else [],
                    "parsed_query": {
                        "query_type": query_type,
                        "intent": intent,
                        "notion_query": notion_query,
                        "git_query": git_query,
                        "keywords": parsed.get("keywords", []),
                        "is_my_query": is_my_query,
                    }
                }
            }
            
            logger.info(f"=== Query complete ===")
            return result

        try:
            return anyio.run(run)
        except Exception as exc:  # pragma: no cover
            logger.error(f"Query error: {exc}", exc_info=True)
            return {"scenario": scenario, "query": query, "error": str(exc), "citations": []}


