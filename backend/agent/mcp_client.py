from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional
from django.conf import settings

logger = logging.getLogger("agent")

try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.session import ClientSession
    MCP_AVAILABLE = True
except Exception as e:
    logger.warning(f"MCP package not available or incorrect version: {e}")
    ClientSession = None  # type: ignore
    StdioServerParameters = None  # type: ignore
    stdio_client = None  # type: ignore
    MCP_AVAILABLE = False


class MCPHarness:
    def __init__(self, notion_cmd: str | None = None, git_cmd: str | None = None):
        self.notion_cmd = notion_cmd or settings.NOTION_MCP_CMD
        self.git_cmd = git_cmd or settings.GIT_MCP_CMD
    
    def _is_user_repo(self, item: Dict[str, Any], username: str) -> bool:
        """
        Check if a GitHub item belongs to the authenticated user's repository.
        Returns True if item is from user's repo, False otherwise.
        """
        if not username:
            return True  # If no username, don't filter
        
        # Check various possible fields for repository ownership
        repo_full_name = None
        repo_owner = None
        
        # Try to extract repo information from different response formats
        if "repository" in item:
            repo = item["repository"]
            if isinstance(repo, dict):
                repo_full_name = repo.get("full_name", "")
                repo_owner = repo.get("owner", {})
                if isinstance(repo_owner, dict):
                    repo_owner = repo_owner.get("login", "")
        elif "repo" in item:
            repo_full_name = item["repo"]
        elif "full_name" in item:
            repo_full_name = item["full_name"]
        
        # Also check path-based extraction (e.g., "owner/repo/path/to/file")
        if not repo_full_name and "path" in item:
            path = item["path"]
            # Path might be in format "owner/repo/path" or just "path"
            if "/" in path:
                parts = path.split("/")
                if len(parts) >= 2:
                    potential_owner = parts[0]
                    if potential_owner.lower() == username.lower():
                        return True
        
        # Check if owner matches authenticated user
        if repo_full_name:
            owner = repo_full_name.split("/")[0] if "/" in repo_full_name else None
            if owner and owner.lower() == username.lower():
                return True
        
        if repo_owner and isinstance(repo_owner, str) and repo_owner.lower() == username.lower():
            return True
        
        # If we can't determine ownership, be conservative and exclude it
        logger.debug(f"Could not determine repo ownership for item: {item.get('path', item.get('name', 'unknown'))}")
        return False

    async def notion_list(self) -> List[Dict[str, Any]]:
        if not self.notion_cmd or not MCP_AVAILABLE:
            if not MCP_AVAILABLE:
                logger.error("MCP package not available - check installation")
            return []
        try:
            parts = self.notion_cmd.split()
            server = StdioServerParameters(command=parts[0], args=parts[1:] if len(parts) > 1 else [])
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    resources_list = []
                    try:
                        resources = await session.list_resources()
                        resources_list = [
                            {"type": "resource", "uri": r.uri, "name": getattr(r, "name", r.uri)}
                            for r in resources.resources
                        ]
                    except Exception as e:
                        logger.debug(f"Resources not available from Notion MCP server: {e}")
                    
                    return [
                        {"type": "tool", "name": t.name, "description": getattr(t, "description", "")}
                        for t in tools.tools
                    ] + resources_list
        except Exception as e:
            logger.error(f"Notion MCP error: {e}", exc_info=True)
            return []

    async def notion_query(self, query: str) -> List[Dict[str, Any]]:
        if not self.notion_cmd:
            logger.warning("Notion MCP command not configured")
            return []
        if not MCP_AVAILABLE:
            logger.error("MCP package not available - check installation")
            return []
        
        logger.info(f"Querying Notion with: {query}")
        logger.info(f"Using command: {self.notion_cmd}")
        
        try:
            parts = self.notion_cmd.split()
            server = StdioServerParameters(command=parts[0], args=parts[1:] if len(parts) > 1 else [])
            logger.debug(f"Connecting to Notion MCP server: {parts[0]} with args: {parts[1:]}")
            
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    logger.debug("Initializing Notion MCP session...")
                    await session.initialize()
                    
                    # List available tools
                    logger.debug("Listing Notion tools...")
                    tools = await session.list_tools()
                    tool_names = [t.name for t in tools.tools]
                    logger.info(f"Available Notion tools: {tool_names}")
                    
                    if not tool_names:
                        logger.warning("No tools available from Notion MCP server")
                        return []
                    
                    # Try search or query tools (works with both official and custom servers)
                    search_tools = ["notion_search", "search", "query", "notion_query", "search_pages", "search_notion"]
                    for tool_name in search_tools:
                        if tool_name in tool_names:
                            try:
                                logger.info(f"Calling Notion tool: {tool_name} with query: {query}")
                                result = await session.call_tool(tool_name, {"query": query})
                                logger.debug(f"Tool {tool_name} returned: {type(result)}")
                                
                                # Parse JSON response
                                if hasattr(result, "content"):
                                    content_list = result.content
                                    logger.debug(f"Content list type: {type(content_list)}, length: {len(content_list) if isinstance(content_list, list) else 'N/A'}")
                                    
                                    if isinstance(content_list, list) and len(content_list) > 0:
                                        first_content = content_list[0]
                                        logger.debug(f"First content type: {type(first_content)}, attributes: {dir(first_content)}")
                                        
                                        if hasattr(first_content, "text"):
                                            try:
                                                text_content = first_content.text
                                                logger.debug(f"Text content (first 200 chars): {text_content[:200]}")
                                                parsed = json.loads(text_content)
                                                logger.info(f"Parsed JSON from {tool_name}: {type(parsed)}")
                                                
                                                # Handle both custom server format and official server format
                                                if isinstance(parsed, dict):
                                                    items = parsed.get("items", parsed.get("results", parsed.get("pages", parsed.get("data", []))))
                                                    if items:
                                                        logger.info(f"Extracted {len(items)} items from {tool_name}")
                                                        return items if isinstance(items, list) else [items]
                                                elif isinstance(parsed, list):
                                                    logger.info(f"Got list of {len(parsed)} items from {tool_name}")
                                                    return parsed
                                            except json.JSONDecodeError as e:
                                                logger.warning(f"JSON parse error for {tool_name}: {e}")
                                                logger.debug(f"Raw content: {first_content.text[:500]}")
                                                # If not JSON, return as text content
                                                return [{"title": first_content.text[:100], "content": first_content.text}]
                                        
                                        # Try to extract text from other content types
                                        texts = []
                                        for idx, content in enumerate(content_list):
                                            logger.debug(f"Processing content {idx}: {type(content)}")
                                            if hasattr(content, "text"):
                                                texts.append(content.text)
                                            elif hasattr(content, "type") and getattr(content, "type", None) == "text":
                                                texts.append(getattr(content, "text", ""))
                                        if texts:
                                            logger.info(f"Extracted {len(texts)} text items")
                                            return [{"title": t[:100], "content": t} for t in texts]
                                
                                # If result is not in expected format, try to extract data
                                if hasattr(result, "content"):
                                    logger.warning(f"Unexpected result format from {tool_name}")
                                    return [{"title": str(result.content)[:100], "content": str(result.content)}]
                            except Exception as e:
                                logger.error(f"Error calling Notion tool {tool_name}: {e}", exc_info=True)
                                continue
                    
                    # Fallback: return available tools info
                    if tools.tools:
                        logger.warning(f"None of the search tools {search_tools} found. Available tools: {tool_names}")
                        return [{"name": t.name, "description": getattr(t, "description", ""), "type": "tool_info"} for t in tools.tools]
                    else:
                        logger.error("No tools available from Notion MCP server")
                        return []
        except Exception as e:
            logger.error(f"Notion query error: {e}", exc_info=True)
            return []

    async def git_list(self) -> List[Dict[str, Any]]:
        """List available tools from Git MCP server"""
        if not self.git_cmd:
            logger.warning("Git MCP command not configured")
            return []
        if not MCP_AVAILABLE:
            logger.error("MCP package not available - check installation")
            return []
        
        try:
            parts = self.git_cmd.split()
            # GitHub MCP server needs GITHUB_PERSONAL_ACCESS_TOKEN env var
            env = os.environ.copy()
            if settings.GITHUB_PERSONAL_ACCESS_TOKEN:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = settings.GITHUB_PERSONAL_ACCESS_TOKEN
                logger.debug("GitHub token configured in environment")
            
            server = StdioServerParameters(
                command=parts[0],
                args=parts[1:] if len(parts) > 1 else [],
                env=env
            )
            logger.debug(f"Connecting to GitHub MCP server: {parts[0]} with args: {parts[1:]}")
            
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    logger.debug("Initializing Git MCP session...")
                    await session.initialize()
                    
                    # List available tools
                    logger.debug("Listing Git tools...")
                    tools = await session.list_tools()
                    tool_names = [t.name for t in tools.tools]
                    logger.info(f"Available Git tools: {tool_names}")
                    
                    return [
                        {"type": "tool", "name": t.name, "description": getattr(t, "description", "")}
                        for t in tools.tools
                    ]
        except Exception as e:
            logger.error(f"Git list error: {e}", exc_info=True)
            return []

    async def git_search(self, query: str, query_type: str = None, is_my_query: bool = False, is_count_query: bool = False) -> List[Dict[str, Any]]:
        if not self.git_cmd:
            logger.warning("Git MCP command not configured")
            return []
        if not MCP_AVAILABLE:
            logger.error("MCP package not available - check installation")
            return []
        
        logger.info(f"Searching Git with: {query}")
        logger.info(f"Using command: {self.git_cmd}")
        
        try:
            parts = self.git_cmd.split()
            # GitHub MCP server needs GITHUB_PERSONAL_ACCESS_TOKEN env var
            # Get current environment and add token if available
            env = os.environ.copy()
            if settings.GITHUB_PERSONAL_ACCESS_TOKEN:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = settings.GITHUB_PERSONAL_ACCESS_TOKEN
                logger.debug("GitHub token configured in environment")
            
            server = StdioServerParameters(
                command=parts[0],
                args=parts[1:] if len(parts) > 1 else [],
                env=env
            )
            logger.debug(f"Connecting to GitHub MCP server: {parts[0]} with args: {parts[1:]}")
            
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    logger.debug("Initializing Git MCP session...")
                    await session.initialize()
                    
                    # List available tools
                    logger.debug("Listing Git tools...")
                    tools = await session.list_tools()
                    tool_names = [t.name for t in tools.tools]
                    logger.info(f"Available Git tools: {tool_names}")
                    
                    if not tool_names:
                        logger.warning("No tools available from Git MCP server")
                        return []
                    
                    # Try GitHub MCP server tools - prioritize based on query type
                    # Use passed query_type if available, otherwise detect from query
                    query_lower = query.lower() if query else ""
                    is_commit_query = query_type == "commit" if query_type else any(word in query_lower for word in ["commit", "committed", "headline", "update", "change"])
                    # Use passed is_my_query if available, otherwise detect from query
                    is_my_query = is_my_query if is_my_query else any(phrase in query_lower for phrase in ["my last", "my recent", "my commits", "my repositories", "my repo", "my code"])
                    # Use passed is_count_query if available, otherwise detect from query
                    is_count_query = is_count_query if is_count_query else any(word in query_lower for word in ["how many", "count", "number of"])
                    
                    # For commit count queries or "my" commit queries, prioritize list_commits
                    if (is_commit_query and is_count_query) or (is_commit_query and is_my_query) or (is_my_query and is_count_query):
                        # For commit-related or "my" queries, prioritize getting user's repos and commits
                        search_tools = [
                            "list_commits",  # GitHub MCP: List commits (requires owner/repo) - MUST be first for count queries
                            "get_me",  # Get user info first to find their repos
                            "search_repositories",  # Find user's repos
                            "search_code",  # Fallback: Search code (scoped to user)
                            "search_issues",  # Fallback: Search issues
                        ]
                    elif is_commit_query or is_my_query:
                        # For commit-related or "my" queries, prioritize getting user's repos and commits
                        search_tools = [
                            "list_commits",  # GitHub MCP: List commits (requires owner/repo)
                            "get_me",  # Get user info first to find their repos
                            "search_repositories",  # Find user's repos
                            "search_code",  # Fallback: Search code (scoped to user)
                            "search_issues",  # Fallback: Search issues
                        ]
                    else:
                        # For code/content queries, use code search first
                        search_tools = [
                            "search_code",  # GitHub MCP: Search code across repositories
                            "search_repositories",  # GitHub MCP: Search repositories
                            "search_issues",  # GitHub MCP: Search issues
                            "list_commits",  # Fallback: List commits
                            "get_file_contents",  # GitHub MCP: Get file contents
                            "list_files",  # Fallback for filesystem server
                            "search",  # Generic search
                            "grep",  # Generic grep
                        ]
                    # Always get user info to scope searches to authenticated user's repos
                    username = None
                    if "get_me" in tool_names:
                        try:
                            user_result = await session.call_tool("get_me", {})
                            if hasattr(user_result, "content") and len(user_result.content) > 0:
                                user_text = user_result.content[0].text if hasattr(user_result.content[0], "text") else str(user_result.content[0])
                                try:
                                    user_data = json.loads(user_text) if isinstance(user_text, str) else user_text
                                    username = user_data.get("login") or user_data.get("name", "")
                                    logger.info(f"Authenticated user: {username} - scoping all searches to this user's repositories")
                                except:
                                    pass
                        except Exception as e:
                            logger.debug(f"Could not get user info: {e}")
                    
                    for tool_name in search_tools:
                        if tool_name in tool_names:
                            try:
                                # Skip get_me if we already have username
                                if tool_name == "get_me" and username:
                                    continue
                                
                                # GitHub MCP server parameter formats
                                if tool_name == "search_code":
                                    # Don't use search_code for commit count queries - those need list_commits
                                    if is_count_query and is_commit_query:
                                        logger.info(f"Skipping search_code for commit count query - need list_commits")
                                        continue
                                    
                                    # Always scope search to authenticated user's repositories ONLY
                                    keywords = [w for w in query.lower().split() if w not in ["what", "implementation", "exists", "about", "the", "a", "an", "commit", "committed", "my", "my"]]
                                    if username:
                                        # Use user: qualifier to restrict to user's repos only
                                        # Also add repo: qualifier if we can determine specific repo from query
                                        search_query = f"user:{username}"
                                        if keywords:
                                            search_query += f" {' '.join(keywords)}"
                                        params = {"query": search_query}
                                        logger.info(f"Scoping code search to user {username}'s repositories ONLY: {search_query}")
                                    elif keywords:
                                        params = {"query": " ".join(keywords)}
                                        logger.info(f"Searching code for keywords: {keywords} (WARNING: Not scoped to user)")
                                    else:
                                        params = {"query": query}
                                        logger.warning(f"Searching code without user scope - may return results from other repos")
                                elif tool_name == "search_repositories":
                                    # Always search user's repos first when username is available
                                    if username:
                                        # If query has additional terms, combine them
                                        keywords = [w for w in query.lower().split() if w not in ["user:", "my", "my", "repositories", "repos"]]
                                        if keywords:
                                            params = {"query": f"user:{username} {' '.join(keywords)}"}
                                        else:
                                            params = {"query": f"user:{username}"}
                                        logger.info(f"Searching for user {username}'s repositories")
                                    else:
                                        params = {"query": query}
                                elif tool_name == "search_issues":
                                    # Scope to user's repos if username is available
                                    if username:
                                        keywords = [w for w in query.lower().split() if w not in ["what", "implementation", "exists", "about", "the", "a", "an"]]
                                        if keywords:
                                            params = {"query": f"user:{username} {' '.join(keywords)}"}
                                        else:
                                            params = {"query": f"user:{username}"}
                                        logger.info(f"Scoping issue search to user {username}'s repositories")
                                    else:
                                        params = {"query": query}
                                elif tool_name == "get_me":
                                    # Get user info - already handled above, skip here
                                    continue
                                
                                elif tool_name == "list_commits":
                                    # List commits requires owner/repo
                                    # Strategy: Use username from above to find their repos, then list commits
                                    logger.info(f"Attempting commit search - finding repositories...")
                                    try:
                                        repos_found = []
                                        
                                        # Step 1: Use username from above, or get it if not available
                                        if not username and "get_me" in tool_names:
                                            try:
                                                user_result = await session.call_tool("get_me", {})
                                                if hasattr(user_result, "content") and len(user_result.content) > 0:
                                                    user_text = user_result.content[0].text if hasattr(user_result.content[0], "text") else str(user_result.content[0])
                                                    try:
                                                        user_data = json.loads(user_text) if isinstance(user_text, str) else user_text
                                                        username = user_data.get("login") or user_data.get("name", "")
                                                        logger.info(f"Found user: {username}")
                                                    except json.JSONDecodeError:
                                                        logger.debug(f"Could not parse user data")
                                            except Exception as e:
                                                logger.debug(f"Could not get user info: {e}")
                                        
                                        # Step 2: Get repositories the token actually has access to
                                        # For fine-grained tokens, we need to verify access by trying to read from each repo
                                        if username and "search_repositories" in tool_names:
                                            try:
                                                repo_result = await session.call_tool("search_repositories", {"query": f"user:{username}"})
                                                if hasattr(repo_result, "content") and len(repo_result.content) > 0:
                                                    repo_text = repo_result.content[0].text if hasattr(repo_result.content[0], "text") else str(repo_result.content[0])
                                                    try:
                                                        repo_data = json.loads(repo_text) if isinstance(repo_text, str) else repo_text
                                                        if isinstance(repo_data, dict) and "items" in repo_data:
                                                            all_repos = repo_data["items"][:20]  # Get more repos to check
                                                        elif isinstance(repo_data, list):
                                                            all_repos = repo_data[:20]
                                                        else:
                                                            all_repos = []
                                                        
                                                        # Verify token access by trying to read from each repository
                                                        # Fine-grained tokens only have access to specified repos
                                                        repos_found = []
                                                        logger.info(f"Verifying token access for {len(all_repos)} repositories...")
                                                        
                                                        for repo in all_repos:
                                                            repo_full_name = repo.get("full_name", "")
                                                            repo_name = repo.get("name", "")
                                                            repo_owner = None
                                                            if isinstance(repo.get("owner"), dict):
                                                                repo_owner = repo.get("owner", {}).get("login", "")
                                                            elif repo.get("owner"):
                                                                repo_owner = str(repo.get("owner"))
                                                            
                                                            if not repo_owner:
                                                                # Extract from full_name
                                                                if repo_full_name and "/" in repo_full_name:
                                                                    repo_owner = repo_full_name.split("/")[0]
                                                                else:
                                                                    repo_owner = username
                                                            
                                                            # Verify token access - use stricter check for fine-grained tokens
                                                            # Public repos allow reading commits without auth, so we need a different approach
                                                            repo_is_private = repo.get("private", False)
                                                            
                                                            if repo_owner and repo_name:
                                                                has_access = False
                                                                
                                                                # For private repos, try list_commits (requires explicit access)
                                                                # For public repos, try get_file_contents or list_branches (more restrictive)
                                                                if repo_is_private and "list_commits" in tool_names:
                                                                    try:
                                                                        await session.call_tool("list_commits", {
                                                                            "owner": repo_owner,
                                                                            "repo": repo_name,
                                                                            "per_page": 1
                                                                        })
                                                                        has_access = True
                                                                        logger.debug(f"Token verified access to private repo {repo_full_name or f'{repo_owner}/{repo_name}'}")
                                                                    except Exception as e:
                                                                        logger.debug(f"Token does NOT have access to private repo {repo_full_name or f'{repo_owner}/{repo_name}'}: {e}")
                                                                        continue
                                                                elif not repo_is_private:
                                                                    # For public repos, try get_file_contents which requires explicit repo access
                                                                    # Even public repos require token access for get_file_contents if token is fine-grained
                                                                    if "get_file_contents" in tool_names:
                                                                        try:
                                                                            # Try to read a common file (README, .gitignore, etc.)
                                                                            await session.call_tool("get_file_contents", {
                                                                                "owner": repo_owner,
                                                                                "repo": repo_name,
                                                                                "path": "README.md"
                                                                            })
                                                                            has_access = True
                                                                            logger.debug(f"Token verified access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'} via get_file_contents")
                                                                        except Exception as e:
                                                                            # If README.md doesn't exist, try .gitignore
                                                                            try:
                                                                                await session.call_tool("get_file_contents", {
                                                                                    "owner": repo_owner,
                                                                                    "repo": repo_name,
                                                                                    "path": ".gitignore"
                                                                                })
                                                                                has_access = True
                                                                                logger.debug(f"Token verified access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'} via .gitignore")
                                                                            except Exception as e2:
                                                                                logger.debug(f"Token does NOT have access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}: {e2}")
                                                                                continue
                                                                    elif "list_branches" in tool_names:
                                                                        # Fallback: try list_branches (also requires explicit access for fine-grained tokens)
                                                                        try:
                                                                            await session.call_tool("list_branches", {
                                                                                "owner": repo_owner,
                                                                                "repo": repo_name
                                                                            })
                                                                            has_access = True
                                                                            logger.debug(f"Token verified access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'} via list_branches")
                                                                        except Exception as e:
                                                                            logger.debug(f"Token does NOT have access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}: {e}")
                                                                            continue
                                                                    else:
                                                                        # Can't verify properly, skip this repo to be safe
                                                                        logger.warning(f"Cannot verify access to {repo_full_name or f'{repo_owner}/{repo_name}'} - no suitable tools available")
                                                                        continue
                                                                
                                                                if has_access:
                                                                    repos_found.append(repo)
                                                            else:
                                                                # Can't determine owner/repo, skip it
                                                                logger.debug(f"Cannot verify access - missing owner or repo name")
                                                                continue
                                                        
                                                        if repos_found:
                                                            logger.info(f"Token has access to {len(repos_found)} repository/repositories: {[r.get('full_name', r.get('name', 'unknown')) for r in repos_found]}")
                                                        else:
                                                            logger.warning(f"Token does not have access to any of the {len(all_repos)} repositories found")
                                                    except Exception as e:
                                                        logger.debug(f"Error parsing repo data: {e}")
                                            except Exception as e:
                                                logger.debug(f"Error searching repos: {e}")
                                        
                                        # Step 3: List commits from found repos
                                        if repos_found:
                                            logger.info(f"Found {len(repos_found)} repos total. Processing commits...")
                                            all_commits = []
                                            total_commits_count = 0
                                            
                                            # For "how many commits" queries, count commits from all repos
                                            is_count_query = any(word in query_lower for word in ["how many", "count", "number of"])
                                            
                                            # For "my repo" (singular) queries, only check the first repo or filtered repo
                                            is_singular_repo_query = any(phrase in query_lower for phrase in ["my repo", "my repository", "name of my", "what is my repo"])
                                            
                                            # If repo filter is set or query is singular, only check first repo
                                            if settings.GITHUB_REPO_FILTER or is_singular_repo_query:
                                                repos_to_check = repos_found[:1]
                                                logger.info(f"Query is singular or repo filter is set - checking only first repo: {repos_to_check[0].get('name', 'unknown') if repos_to_check else 'none'}")
                                            else:
                                                repos_to_check = repos_found[:10] if is_count_query else repos_found[:3]  # Check more repos for count queries
                                            logger.info(f"Checking {len(repos_to_check)} repos for commits: {[r.get('name', 'unknown') for r in repos_to_check]}")
                                            
                                            if not repos_to_check:
                                                logger.error("repos_to_check is empty even though repos_found has items!")
                                                logger.error(f"repos_found: {repos_found}")
                                                logger.error(f"is_count_query: {is_count_query}")
                                            
                                            for repo in repos_to_check:
                                                try:
                                                    logger.debug(f"Processing repo: {repo}")
                                                    
                                                    # Extract owner - try multiple methods
                                                    owner = None
                                                    if isinstance(repo.get("owner"), dict):
                                                        owner = repo.get("owner", {}).get("login", "")
                                                    elif repo.get("owner"):
                                                        owner = str(repo.get("owner"))
                                                    else:
                                                        # Fallback: extract from full_name (e.g., "premdwivedi/PixSolve")
                                                        full_name = repo.get("full_name", "")
                                                        if full_name and "/" in full_name:
                                                            owner = full_name.split("/")[0]
                                                        # If still no owner, use the authenticated username
                                                        if not owner and username:
                                                            owner = username
                                                    
                                                    repo_name = repo.get("name", "")
                                                    
                                                    logger.info(f"Extracted owner: '{owner}', repo_name: '{repo_name}' from repo: {repo.get('full_name', 'unknown')}")
                                                    
                                                    if not owner or not repo_name:
                                                        logger.warning(f"Skipping repo - missing owner or repo_name. Owner: '{owner}', Repo: '{repo_name}'. Repo data: {repo}")
                                                        continue
                                                    
                                                    logger.info(f"Listing commits from {owner}/{repo_name}...")
                                                    try:
                                                        # Build parameters - only include non-empty values
                                                        params = {
                                                            "owner": owner,
                                                            "repo": repo_name
                                                        }
                                                        # Only add optional parameters if they have values
                                                        # Empty strings might cause the API to fail
                                                        logger.debug(f"Calling list_commits with params: {params}")
                                                        commits_result = await session.call_tool("list_commits", params)
                                                        logger.info(f"Received commits_result from {owner}/{repo_name}, type: {type(commits_result)}")
                                                        logger.debug(f"commits_result has content attr: {hasattr(commits_result, 'content')}")
                                                        if hasattr(commits_result, "content"):
                                                            logger.debug(f"commits_result.content length: {len(commits_result.content) if hasattr(commits_result, 'content') else 'N/A'}")
                                                        
                                                        if hasattr(commits_result, "content") and len(commits_result.content) > 0:
                                                            commits_text = commits_result.content[0].text if hasattr(commits_result.content[0], "text") else str(commits_result.content[0])
                                                            logger.info(f"Commits response from {owner}/{repo_name}: {commits_text[:1000]}...")
                                                            try:
                                                                commits_data = json.loads(commits_text) if isinstance(commits_text, str) else commits_text
                                                                logger.debug(f"Parsed commits_data type: {type(commits_data)}")
                                                                
                                                                # Handle different response formats
                                                                if isinstance(commits_data, list):
                                                                    commits_list = commits_data
                                                                elif isinstance(commits_data, dict):
                                                                    # Try common keys
                                                                    commits_list = commits_data.get("items", commits_data.get("data", commits_data.get("commits", [])))
                                                                    if not commits_list and len(commits_data) == 1:
                                                                        # Might be wrapped in a single key
                                                                        first_value = list(commits_data.values())[0]
                                                                        if isinstance(first_value, list):
                                                                            commits_list = first_value
                                                                else:
                                                                    commits_list = []
                                                                
                                                                logger.info(f"Extracted {len(commits_list)} commits from {owner}/{repo_name}")
                                                                
                                                                if commits_list:
                                                                    repo_commit_count = len(commits_list)
                                                                    total_commits_count += repo_commit_count
                                                                    logger.info(f"Found {repo_commit_count} commits in {owner}/{repo_name}")
                                                                    
                                                                    # For count queries, just track the count
                                                                    if is_count_query:
                                                                        all_commits.append({
                                                                            "repo": f"{owner}/{repo_name}",
                                                                            "count": repo_commit_count,
                                                                            "commits": commits_list[:5]  # Sample commits
                                                                        })
                                                                    # For "my last commit" queries, get the most recent commit(s)
                                                                    elif is_my_query and "last" in query_lower:
                                                                        if commits_list:
                                                                            all_commits.append(commits_list[0])
                                                                            logger.info(f"Found most recent commit in {owner}/{repo_name}: {commits_list[0].get('sha', '')[:8]}")
                                                                    else:
                                                                        # For "my" queries without keywords, return all commits
                                                                        if is_my_query:
                                                                            all_commits.extend(commits_list)
                                                                            logger.info(f"Returning all {len(commits_list)} commits from {owner}/{repo_name} for 'my' query")
                                                                        else:
                                                                            # Filter commits by message containing query keywords
                                                                            query_keywords = [w.lower() for w in query.split() if w.lower() not in ["what", "implementation", "exists", "about", "the", "a", "an", "my", "my", "how", "many", "are", "there", "in", "github", "repo"]]
                                                                            if query_keywords:
                                                                                filtered = [c for c in commits_list if any(kw in str(c.get("commit", {}).get("message", "")).lower() for kw in query_keywords)]
                                                                                if filtered:
                                                                                    all_commits.extend(filtered[:10])  # Limit per repo
                                                                                    logger.info(f"Found {len(filtered)} matching commits in {owner}/{repo_name}")
                                                                                else:
                                                                                    # No matches, return empty
                                                                                    logger.info(f"No keyword matches found in {owner}/{repo_name}")
                                                                            else:
                                                                                # No keywords, return recent commits
                                                                                all_commits.extend(commits_list[:30])
                                                                                logger.info(f"Returning {len(commits_list[:30])} recent commits from {owner}/{repo_name}")
                                                                else:
                                                                    logger.warning(f"No commits found in {owner}/{repo_name} - commits_list is empty. Response structure: {type(commits_data)}")
                                                                    if isinstance(commits_data, dict):
                                                                        logger.warning(f"Response keys: {list(commits_data.keys())}")
                                                                    logger.debug(f"Full response: {commits_text[:2000]}")
                                                            except Exception as e:
                                                                logger.error(f"Error parsing commits from {owner}/{repo_name}: {e}", exc_info=True)
                                                                logger.debug(f"Raw commits text: {commits_text[:1000]}")
                                                        else:
                                                            logger.warning(f"No content in commits_result for {owner}/{repo_name}. Result type: {type(commits_result)}")
                                                            if hasattr(commits_result, "content"):
                                                                logger.warning(f"commits_result.content is empty or None. Length: {len(commits_result.content) if commits_result.content else 0}")
                                                    except Exception as e:
                                                        logger.error(f"Error calling list_commits for {owner}/{repo_name}: {e}", exc_info=True)
                                                        raise  # Re-raise to be caught by outer except
                                                except Exception as e:
                                                    logger.error(f"Error processing repo {repo.get('name', 'unknown')}: {e}", exc_info=True)
                                                    continue  # Continue to next repo
                                            
                                            logger.info(f"After processing all repos: all_commits={len(all_commits)}, total_commits_count={total_commits_count}")
                                            
                                            if all_commits or total_commits_count > 0:
                                                # For count queries, return summary with total
                                                if is_count_query:
                                                    logger.info(f"Total commits found: {total_commits_count} across {len(all_commits)} repos")
                                                    return [{
                                                        "total_count": total_commits_count,
                                                        "repos": all_commits,
                                                        "summary": f"Found {total_commits_count} commits across {len(all_commits)} repositories"
                                                    }]
                                                
                                                logger.info(f"Found {len(all_commits)} total commits matching query")
                                                # Sort by date (most recent first) for "my last commit" queries
                                                if is_my_query and "last" in query_lower:
                                                    all_commits.sort(key=lambda x: x.get("commit", {}).get("author", {}).get("date", ""), reverse=True)
                                                    return all_commits[:1]  # Return only the most recent
                                                return all_commits
                                            else:
                                                logger.warning(f"No commits found after processing {len(repos_to_check)} repos. This might indicate:")
                                                logger.warning(f"  - Repos have no commits")
                                                logger.warning(f"  - API calls are failing silently")
                                                logger.warning(f"  - Response format is unexpected")
                                        else:
                                            logger.warning(f"No repos found to check for commits")
                                        
                                        # If no commits found and this is a commit count query, don't fall back to search_code
                                        if is_count_query and is_commit_query:
                                            logger.warning(f"No commits found for commit count query - returning empty result")
                                            return [{
                                                "total_count": 0,
                                                "repos": [],
                                                "summary": "No commits found in your repositories. Please check if the repositories have commits and if your token has the necessary permissions."
                                            }]
                                        
                                        # If no commits found, skip and try search_code (but not for commit count queries)
                                        logger.debug(f"No commits found, trying search_code as fallback")
                                        continue
                                    except Exception as e:
                                        logger.debug(f"Error in commit search: {e}")
                                        continue
                                elif tool_name == "get_commit":
                                    # Get specific commit - would need SHA
                                    params = {"owner": "", "repo": "", "sha": ""}
                                    if not params.get("sha"):
                                        logger.debug(f"Skipping {tool_name} - requires commit SHA")
                                        continue
                                elif tool_name == "get_file_contents":
                                    # Try to extract repo and path from query, or use default
                                    params = {"owner": "github", "repo": "github-mcp-server", "path": query}
                                else:
                                    # Fallback for other tools
                                    params = {"query": query, "pattern": query}
                                
                                logger.info(f"Calling GitHub tool: {tool_name} with params: {params}")
                                result = await session.call_tool(tool_name, params)
                                logger.debug(f"Tool {tool_name} returned: {type(result)}")
                                
                                if hasattr(result, "content"):
                                    content_list = result.content
                                    logger.debug(f"Content list type: {type(content_list)}, length: {len(content_list) if isinstance(content_list, list) else 'N/A'}")
                                    
                                    if isinstance(content_list, list) and len(content_list) > 0:
                                        items = []
                                        for idx, content in enumerate(content_list):
                                            logger.debug(f"Processing Git content {idx}: {type(content)}")
                                            if hasattr(content, "text"):
                                                try:
                                                    parsed = json.loads(content.text)
                                                    logger.debug(f"Parsed JSON item: {type(parsed)}")
                                                    
                                                    # For search_repositories, verify token access to each repo
                                                    # Fine-grained tokens only have access to specified repos
                                                    if tool_name == "search_repositories" and isinstance(parsed, (list, dict)):
                                                        repos_to_verify = parsed if isinstance(parsed, list) else [parsed]
                                                        verified_repos = []
                                                        
                                                        for repo in repos_to_verify:
                                                            repo_full_name = repo.get("full_name", "")
                                                            repo_name = repo.get("name", "")
                                                            repo_owner = None
                                                            if isinstance(repo.get("owner"), dict):
                                                                repo_owner = repo.get("owner", {}).get("login", "")
                                                            elif repo.get("owner"):
                                                                repo_owner = str(repo.get("owner"))
                                                            
                                                            if not repo_owner and repo_full_name and "/" in repo_full_name:
                                                                repo_owner = repo_full_name.split("/")[0]
                                                            
                                                            # Verify token access - use stricter check for fine-grained tokens
                                                            repo_is_private = repo.get("private", False)
                                                            
                                                            if repo_owner and repo_name:
                                                                has_access = False
                                                                
                                                                # For private repos, try list_commits (requires explicit access)
                                                                # For public repos, try get_file_contents (more restrictive, requires explicit token access)
                                                                if repo_is_private and "list_commits" in tool_names:
                                                                    try:
                                                                        await session.call_tool("list_commits", {
                                                                            "owner": repo_owner,
                                                                            "repo": repo_name,
                                                                            "per_page": 1
                                                                        })
                                                                        has_access = True
                                                                        logger.debug(f"Token verified access to private repo {repo_full_name or f'{repo_owner}/{repo_name}'}")
                                                                    except Exception as e:
                                                                        logger.debug(f"Token does NOT have access to private repo {repo_full_name or f'{repo_owner}/{repo_name}'}: {e}")
                                                                        continue
                                                                elif not repo_is_private:
                                                                    # For public repos, use get_file_contents which requires explicit repo access
                                                                    if "get_file_contents" in tool_names:
                                                                        try:
                                                                            await session.call_tool("get_file_contents", {
                                                                                "owner": repo_owner,
                                                                                "repo": repo_name,
                                                                                "path": "README.md"
                                                                            })
                                                                            has_access = True
                                                                            logger.debug(f"Token verified access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}")
                                                                        except Exception as e:
                                                                            try:
                                                                                await session.call_tool("get_file_contents", {
                                                                                    "owner": repo_owner,
                                                                                    "repo": repo_name,
                                                                                    "path": ".gitignore"
                                                                                })
                                                                                has_access = True
                                                                                logger.debug(f"Token verified access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}")
                                                                            except Exception as e2:
                                                                                logger.debug(f"Token does NOT have access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}: {e2}")
                                                                                continue
                                                                    elif "list_branches" in tool_names:
                                                                        try:
                                                                            await session.call_tool("list_branches", {
                                                                                "owner": repo_owner,
                                                                                "repo": repo_name
                                                                            })
                                                                            has_access = True
                                                                            logger.debug(f"Token verified access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}")
                                                                        except Exception as e:
                                                                            logger.debug(f"Token does NOT have access to public repo {repo_full_name or f'{repo_owner}/{repo_name}'}: {e}")
                                                                            continue
                                                                    else:
                                                                        logger.warning(f"Cannot verify access to {repo_full_name or f'{repo_owner}/{repo_name}'} - no suitable tools")
                                                                        continue
                                                                
                                                                if has_access:
                                                                    verified_repos.append(repo)
                                                            else:
                                                                logger.debug(f"Cannot verify access - missing owner or repo name")
                                                                continue
                                                        
                                                        if verified_repos:
                                                            if isinstance(parsed, list):
                                                                items.extend(verified_repos)
                                                            else:
                                                                items.append(verified_repos[0])
                                                            logger.info(f"Verified token access to {len(verified_repos)} repository/repositories: {[r.get('full_name', r.get('name', 'unknown')) for r in verified_repos]}")
                                                        continue
                                                    
                                                    # Filter results to only include items from authenticated user's repositories
                                                    if isinstance(parsed, list):
                                                        filtered = []
                                                        for item in parsed:
                                                            # Check if item belongs to authenticated user's repo
                                                            if username and self._is_user_repo(item, username):
                                                                filtered.append(item)
                                                            elif not username:
                                                                # If no username, include all (but log warning)
                                                                filtered.append(item)
                                                        items.extend(filtered)
                                                        if len(filtered) < len(parsed):
                                                            logger.info(f"Filtered {len(parsed) - len(filtered)} items not from user {username}'s repositories")
                                                    elif isinstance(parsed, dict):
                                                        # Check if single item belongs to user's repo
                                                        if username and self._is_user_repo(parsed, username):
                                                            items.append(parsed)
                                                        elif not username:
                                                            items.append(parsed)
                                                        else:
                                                            logger.debug(f"Filtered out item not from user {username}'s repository")
                                                except json.JSONDecodeError:
                                                    logger.debug(f"Non-JSON text content: {content.text[:100]}")
                                                    items.append({"content": content.text, "path": query, "title": query})
                                            else:
                                                items.append({"content": str(content), "path": query, "title": query})
                                        if items:
                                            logger.info(f"Extracted {len(items)} items from {tool_name} (filtered to user's repos)")
                                            return items
                                    return content_list if isinstance(content_list, list) else [content_list]
                            except Exception as e:
                                logger.error(f"Error calling Git tool {tool_name}: {e}", exc_info=True)
                                continue
                    
                    # Fallback: return available tools info
                    if tools.tools:
                        logger.warning(f"None of the search tools {search_tools} found. Available tools: {tool_names}")
                        return [{"name": t.name, "description": getattr(t, "description", ""), "type": "tool_info"} for t in tools.tools]
                    else:
                        logger.error("No tools available from Git MCP server")
                        return []
        except Exception as e:
            logger.error(f"Git search error: {e}", exc_info=True)
            return []


