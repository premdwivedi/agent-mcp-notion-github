from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger("agent")

try:
    from langchain_openai import ChatOpenAI
except Exception:  # fallback if missing at install time
    ChatOpenAI = None  # type: ignore


def parse_query(query: str) -> Dict[str, Any]:
    logger.info(f"Parsing query with NLP: {query}")
    
    # Use OpenAI if available
    if ChatOpenAI and settings.OPENAI_API_KEY:
        try:
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=settings.OPENAI_API_KEY,
            )
            
            system_prompt = """You are a query parsing assistant that converts natural language queries into optimized search queries for GitHub and Notion.

Your task is to:
1. Understand the user's intent (finding commits, code, files, issues, repositories, or general info)
2. Extract relevant keywords and search terms
3. Construct optimized queries for:
   - GitHub: Can use search_code, search_repositories, search_issues, list_commits, etc.
   - Notion: Can use search for pages, databases, content

GitHub Query Guidelines:
- For commits: Extract keywords that might appear in commit messages (e.g., "cuncurrently", "authentication", "bug fix")
- For code: Extract function names, variable names, or code patterns
- For files: Use file paths or names
- For issues: Extract issue-related keywords
- For "my" queries: Just extract keywords - the system will automatically scope to user's repos
- DO NOT use placeholders like {username} or {repo_name} - just use keywords
- Remove filler words like "find", "the", "github", "commit details", "how many", "are there", etc.

Notion Query Guidelines:
- Extract key concepts and terms
- Focus on titles, content keywords, or database property names
- Remove filler words

Return your response as JSON with this exact structure:
{
  "notion_query": "optimized search query for Notion",
  "git_query": "optimized search query for GitHub",
  "query_type": "commit|code|file|issue|repository|general",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "is_my_query": false,
  "intent": "Brief description of what the user is looking for"
}

Be specific and extract the most relevant search terms. Remove filler words and focus on actionable keywords."""
            
            user_prompt = f"""Parse this natural language query and construct optimized queries:

User Query: {query}

Return the parsed query structure as JSON."""
            
            logger.info("Calling OpenAI for query parsing...")
            msg = llm.invoke([
                ("system", system_prompt),
                ("user", user_prompt),
            ])
            
            logger.info(f"OpenAI parsing response received: {msg.content[:200]}...")
            
            # Parse JSON response
            try:
                content = msg.content.strip()  # type: ignore[attr-defined]
                if content.startswith("```"):
                    # Extract JSON from code block
                    lines = content.split("\n")
                    json_lines = []
                    in_json = False
                    for line in lines:
                        if line.strip().startswith("```"):
                            in_json = not in_json
                            continue
                        if in_json:
                            json_lines.append(line)
                    content = "\n".join(json_lines)
                elif content.startswith("```json"):
                    content = content[7:]
                    if content.endswith("```"):
                        content = content[:-3]
                
                parsed = json.loads(content.strip())
                logger.info(f"Successfully parsed query: type={parsed.get('query_type')}, keywords={parsed.get('keywords')}")
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {e}")
                logger.error(f"Response content: {content[:500]}")
                # Fall through to fallback
        except Exception as e:
            logger.error(f"OpenAI query parsing error: {e}", exc_info=True)
            # Fall through to fallback
    
    # Fallback: Simple keyword extraction
    logger.info("Using keyword-based fallback query parsing...")
    
    # Extract keywords (remove common stop words)
    stop_words = {"find", "the", "github", "commit", "details", "corresponding", "to", "for", "in", "on", "at", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "should", "could", "may", "might", "must"}
    words = query.lower().split()
    keywords = [w.strip(".,!?;:'\"()[]{}") for w in words if w.strip(".,!?;:'\"()[]{}") not in stop_words and len(w.strip(".,!?;:'\"()[]{}")) > 2]
    
    # Detect query type
    query_lower = query.lower()
    if any(word in query_lower for word in ["commit", "committed", "commits"]):
        query_type = "commit"
    elif any(word in query_lower for word in ["issue", "issues", "bug", "bug report"]):
        query_type = "issue"
    elif any(word in query_lower for word in ["repository", "repo", "repositories", "repos"]):
        query_type = "repository"
    elif any(word in query_lower for word in ["file", "files", "path", "directory"]):
        query_type = "file"
    elif any(word in query_lower for word in ["code", "function", "class", "method", "variable"]):
        query_type = "code"
    else:
        query_type = "general"
    
    # Detect "my" queries
    is_my_query = any(phrase in query_lower for phrase in ["my last", "my recent", "my commits", "my repositories", "my repo", "my code", "my"])
    
    # Construct queries
    notion_query = " ".join(keywords) if keywords else query
    git_query = " ".join(keywords) if keywords else query
    
    return {
        "notion_query": notion_query,
        "git_query": git_query,
        "query_type": query_type,
        "keywords": keywords,
        "is_my_query": is_my_query,
        "intent": f"Search for {query_type} related to: {', '.join(keywords[:5])}" if keywords else "General search"
    }


def correlate(notion_items: List[Dict[str, Any]], git_items: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    logger.info(f"Correlating {len(notion_items)} Notion items and {len(git_items)} Git items for query: {query}")
    
    if not notion_items and not git_items:
        logger.warning("No data from either Notion or Git - returning empty result")
        return {
            "summary": "I couldn't find any relevant information in Notion or Git for this query. Please ensure MCP servers are properly configured and have access to the relevant data.",
            "citations": [],
        }
    
    # Use OpenAI if available
    if ChatOpenAI and settings.OPENAI_API_KEY:
        try:
            logger.info("Using OpenAI for correlation...")
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=settings.OPENAI_API_KEY,
            )
            
            system_prompt = """You are an intelligent assistant that correlates documentation from Notion with code from Git repositories.

Your task is to:
1. Analyze the Notion items (pages, databases, documentation)
2. Analyze the Git items (files, code, commits)
3. Find connections between them based on the user's query
4. Provide a clear, concise summary
5. Cite sources with confidence scores

Return your response as JSON with this exact structure:
{
  "summary": "A clear, concise summary explaining how the Notion documentation relates to the Git code, addressing the user's query",
  "citations": [
    {
      "source": "notion" or "git",
      "title": "Title or name of the item",
      "ref": "URL, path, or identifier",
      "confidence": 0.0 to 1.0
    }
  ]
}

Be specific about what you found and how items relate to each other."""
            
            user_prompt = f"""User Query: {query}

Notion Items ({len(notion_items)}):
{json.dumps(notion_items, indent=2) if notion_items else "No Notion items found"}

Git Items ({len(git_items)}):
{json.dumps(git_items, indent=2) if git_items else "No Git items found"}

Please analyze these items and provide a correlation summary with citations."""
            
            logger.info("Calling OpenAI API...")
            msg = llm.invoke([
                ("system", system_prompt),
                ("user", user_prompt),
            ])
            
            logger.info(f"OpenAI response received: {msg.content[:200]}...")
            
            try:
                content = msg.content.strip()  # type: ignore[attr-defined]
                if content.startswith("```"):
                    # Extract JSON from code block
                    lines = content.split("\n")
                    json_lines = []
                    in_json = False
                    for line in lines:
                        if line.strip().startswith("```"):
                            in_json = not in_json
                            continue
                        if in_json:
                            json_lines.append(line)
                    content = "\n".join(json_lines)
                elif content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                    if content.endswith("```"):
                        content = content[:-3]
                
                data = json.loads(content.strip())
                logger.info(f"Successfully parsed OpenAI response: {len(data.get('citations', []))} citations")
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {e}")
                logger.error(f"Response content: {content[:500]}")
                summary = content if content else "Received response from OpenAI but couldn't parse it as JSON."
                return {"summary": summary, "citations": []}
        except Exception as e:
            logger.error(f"OpenAI correlation error: {e}", exc_info=True)
            # Fall through to fallback
    
    logger.info("Using keyword-based fallback correlation...")
    
    def score(item: Dict[str, Any]) -> float:
        query_words = set(query.lower().split())
        text = (str(item.get("title", "")) + " " + 
                str(item.get("content", "")) + " " + 
                str(item.get("name", "")) + " " +
                str(item.get("path", "")) + " " +
                str(item)).lower()
        text_words = set(text.split())
        if not query_words:
            return 0.0
        overlap = len(query_words.intersection(text_words))
        return overlap / len(query_words)
    
    cited: List[Dict[str, Any]] = []
    for it in sorted(notion_items, key=score, reverse=True)[:5]:
        score_val = score(it)
        if score_val > 0:
            cited.append({
                "source": "notion",
                "title": it.get("title") or it.get("name") or it.get("id") or "Notion Item",
                "ref": it.get("url") or it.get("id") or it.get("ref") or "",
                "confidence": min(0.9, 0.3 + score_val * 0.5),
            })
    
    for it in sorted(git_items, key=score, reverse=True)[:5]:
        score_val = score(it)
        if score_val > 0:
            cited.append({
                "source": "git",
                "title": it.get("title") or it.get("name") or it.get("path") or "Git Item",
                "ref": it.get("path") or it.get("commit") or it.get("ref") or "",
                "confidence": min(0.9, 0.3 + score_val * 0.5),
            })
    
    if cited:
        summary = f"Found {len([c for c in cited if c['source'] == 'notion'])} relevant Notion items and {len([c for c in cited if c['source'] == 'git'])} relevant Git items related to '{query}'. "
        if cited:
            top_item = cited[0]
            summary += f"Most relevant: {top_item['title']} ({top_item['source']})."
    else:
        summary = f"No direct matches found for '{query}' in the available Notion and Git data. The MCP servers may need to be configured or the query may need to be more specific."
    
    logger.info(f"Fallback correlation: {len(cited)} citations")
    return {
        "summary": summary,
        "citations": cited,
    }




