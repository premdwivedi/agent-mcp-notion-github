# MCP Agent - Technical Documentation

## Conceptual Explanation: How the Agent Functions

### Overview

The MCP Agent is an intelligent system that bridges documentation (Notion) and code (GitHub) by using the Model Context Protocol (MCP) to connect to external data sources, and OpenAI to provide intelligent reasoning and correlation.

### Architecture Flow

```
User Query
    ↓
[NLP Query Parser] ← OpenAI API
    ↓
    ├─→ Optimized Notion Query
    └─→ Optimized GitHub Query
    ↓
[MCP Client] → Notion MCP Server → Notion API
[MCP Client] → GitHub MCP Server → GitHub API
    ↓
    ├─→ Notion Results (pages, databases, content)
    └─→ GitHub Results (commits, code, repositories, issues)
    ↓
[AI Correlation Engine] ← OpenAI API
    ↓
Correlated Response with Citations
    ↓
User Interface (React Chat)
```

### Detailed Flow: Query → Retrieval → Reasoning → Response

#### 1. Query Input (User → Frontend)

The user submits a natural language query through the React chat interface. Examples:
- "Show all active tasks for API v2 and where they are implemented"
- "What documentation exists about user authentication?"
- "How many commits are there in my GitHub repo?"

**Component**: `frontend/src/pages/Chat.tsx`
- Captures user input
- Sends POST request to `/api/agent/query`
- Displays response with citations

#### 2. Query Parsing (NLP Preprocessing)

The raw query is processed using OpenAI's GPT-4o-mini to extract:
- **Query Type**: commit, code, file, issue, repository, or general
- **Keywords**: Relevant search terms extracted from the query
- **Optimized Queries**: Separate queries tailored for Notion and GitHub
- **Intent Detection**: Understanding if the query is about "my" repositories, count queries, etc.

**Component**: `backend/agent/reasoning.py` → `parse_query()`

**Example Transformation**:
```
Input: "How many commits are there in my GitHub repo?"
↓
{
  "notion_query": "",
  "git_query": "commits",
  "query_type": "commit",
  "keywords": ["commits"],
  "is_my_query": true,
  "intent": "User is looking for the number of commits in their GitHub repository"
}
```

**How OpenAI is Used**:
- System prompt instructs the LLM to extract keywords and construct optimized queries
- Removes filler words, focuses on actionable search terms
- Detects query patterns (e.g., "my", "count", "how many")

#### 3. Data Retrieval (MCP Integration)

The agent connects to two MCP servers simultaneously via stdio (standard input/output):

##### 3a. Notion MCP Server

**Connection**: Custom Python MCP server (`backend/agent/notion_mcp_server.py`)
- Uses Notion API client with internal integration token
- Exposes tools: `notion_search`, `notion_list_pages`, `notion_get_page`
- Searches pages, databases, and content based on optimized query

**Component**: `backend/agent/mcp_client.py` → `notion_query()`

**Process**:
1. Spawns Python MCP server process with Notion token
2. Establishes stdio connection
3. Lists available tools
4. Calls `notion_search` with optimized query
5. Parses JSON response containing Notion pages/databases

##### 3b. GitHub MCP Server

**Connection**: Official GitHub MCP Server (Docker container)
- Uses GitHub Personal Access Token for authentication
- Exposes 40+ tools including: `search_code`, `search_repositories`, `list_commits`, `get_me`, etc.
- Accesses GitHub API without cloning repositories

**Component**: `backend/agent/mcp_client.py` → `git_search()`

**Process**:
1. Spawns Docker container with GitHub token
2. Establishes stdio connection
3. Gets authenticated user info via `get_me`
4. For "my" queries: Scopes searches to user's repositories using `user:{username}`
5. For commit queries: Uses `list_commits` with owner/repo extracted from `search_repositories`
6. Parses JSON responses containing commits, code, repositories, or issues

**Key Features**:
- **User Scoping**: Automatically scopes all searches to authenticated user's repositories
- **Commit Search Strategy**: Prioritizes `list_commits` for commit-related queries
- **Smart Fallback**: Falls back to `search_code` if specialized tools fail

#### 4. AI Correlation (Reasoning)

The retrieved data from both sources is correlated using OpenAI to provide contextual, reasoned answers.

**Component**: `backend/agent/reasoning.py` → `correlate()`

**Process**:
1. **Input Validation**: Checks if data exists from either source
2. **OpenAI Correlation**:
   - Builds comprehensive prompt with:
     - User's original query
     - All Notion items (pages, databases, content)
     - All GitHub items (commits, code, repositories, issues)
   - Instructs LLM to:
     - Analyze items from both sources
     - Find connections between documentation and code
     - Provide a clear summary
     - Cite sources with confidence scores
3. **Fallback Correlation**: If OpenAI fails, uses keyword-based matching
   - Scores items by keyword overlap
   - Generates basic summary with citations

**Output Structure**:
```json
{
  "summary": "Clear explanation correlating Notion docs with GitHub code",
  "citations": [
    {
      "source": "notion" or "git",
      "title": "Item title",
      "ref": "URL or path",
      "confidence": 0.0-1.0
    }
  ]
}
```

#### 5. Response Generation (Frontend Display)

The correlated response is returned to the frontend and displayed with:
- **Summary**: AI-generated explanation
- **Citations**: Clickable references to Notion pages and GitHub files
- **Confidence Scores**: Indication of relevance (0-100%)

**Component**: `frontend/src/pages/Chat.tsx`
- Renders messages in chat interface
- Displays citations below each response
- Shows loading state during processing

---

## Demonstration: MCP Server Connection and Example Scenarios

### Prerequisites Setup

1. **Environment Configuration** (`.env`):
```env
OPENAI_API_KEY=sk-...
NOTION_TOKEN=ntn_...
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
NOTION_MCP_CMD=python agent/notion_mcp_server.py --token ntn_...
GIT_MCP_CMD=docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... ghcr.io/github/github-mcp-server
```

2. **Health Check**:
```bash
curl http://localhost:8000/api/health/mcp
```

**Expected Response**:
```json
{
  "ok": true,
  "details": {
    "notion_configured": true,
    "git_configured": true,
    "notion_available_tools": ["notion_search", "notion_list_pages", "notion_get_page"],
    "git_available_tools": ["search_code", "list_commits", "get_me", ...],
    "notion_items": 1,
    "git_results": 1
  }
}
```

### Scenario A: Project Traceability

**Query**: "Show me all the active Notion tasks for 'API v2' and where their implementation exists in the Git repository."

**Flow**:

1. **Query Parsing**:
   - Extracts: `query_type: "general"`, `keywords: ["API", "v2", "tasks", "implementation"]`
   - Notion query: `"API v2 tasks"`
   - GitHub query: `"API v2 implementation"`

2. **Notion Retrieval**:
   - Calls `notion_search("API v2 tasks")`
   - Returns pages/databases matching "API v2"
   - Example result:
     ```json
     {
       "title": "API v2 Development Tasks",
       "url": "https://notion.so/...",
       "type": "page",
       "content": "Tasks: Authentication, Payment flow, User management"
     }
     ```

3. **GitHub Retrieval**:
   - Gets authenticated user: `premdwivedi`
   - Calls `search_code("user:premdwivedi API v2 implementation")`
   - Returns code files matching keywords
   - Example result:
     ```json
     {
       "path": "src/api/v2/auth.py",
       "content": "class AuthV2: ...",
       "repository": "premdwivedi/my-project"
     }
     ```

4. **Correlation**:
   - OpenAI analyzes both results
   - Identifies connections:
     - Notion task "Authentication" → GitHub file `auth.py`
     - Notion task "Payment flow" → GitHub file `payment.py`
   - Generates summary with citations

5. **Response**:
   ```
   Summary: Found 3 active tasks in Notion for API v2:
   1. Authentication - Implemented in src/api/v2/auth.py
   2. Payment flow - Implemented in src/api/v2/payment.py
   3. User management - Implemented in src/api/v2/user.py

   Citations:
   [notion] API v2 Development Tasks — https://notion.so/...
   [git] src/api/v2/auth.py — premdwivedi/my-project
   [git] src/api/v2/payment.py — premdwivedi/my-project
   ```

### Scenario B: Documentation vs Implementation Check

**Query**: "According to the Notion page titled 'User Authentication Flow', does the Git repository show a matching implementation?"

**Flow**:

1. **Query Parsing**:
   - Extracts: `query_type: "general"`, `keywords: ["User", "Authentication", "Flow"]`
   - Notion query: `"User Authentication Flow"`
   - GitHub query: `"User Authentication Flow implementation"`

2. **Notion Retrieval**:
   - Calls `notion_search("User Authentication Flow")`
   - Finds specific page with title match
   - Retrieves page content via `notion_get_page(page_id)`
   - Example result:
     ```json
     {
       "title": "User Authentication Flow",
       "content": "1. User submits credentials\n2. Validate JWT token\n3. Return user session",
       "url": "https://notion.so/..."
     }
     ```

3. **GitHub Retrieval**:
   - Searches code for: `"user:premdwivedi authentication JWT"`
   - Finds implementation files
   - Example result:
     ```json
     {
       "path": "src/auth/login.py",
       "content": "def authenticate_user(username, password):\n    token = validate_jwt(...)\n    return session",
       "repository": "premdwivedi/my-project"
     }
     ```

4. **Correlation**:
   - OpenAI compares:
     - Notion documentation: 3-step flow (credentials → JWT → session)
     - GitHub code: `authenticate_user()` function with JWT validation
   - Determines match/mismatch

5. **Response**:
   ```
   Summary: The Git implementation matches the Notion documentation. 
   The code in src/auth/login.py implements the 3-step authentication 
   flow described in the Notion page: user credentials → JWT validation → session return.

   Citations:
   [notion] User Authentication Flow — https://notion.so/...
   [git] src/auth/login.py — premdwivedi/my-project (95% confidence)
   ```

---

## Summary Write-Up

### How the OpenAI API Key is Utilized

The OpenAI API key is used in **two critical stages** of the agent's operation:

#### 1. Query Parsing (NLP Preprocessing)

**Purpose**: Transform natural language queries into optimized search queries

**Model**: GPT-4o-mini (fast, cost-effective)

**Usage**:
- **System Prompt**: Instructs the LLM to extract keywords, detect query types, and construct optimized queries
- **Input**: Raw user query (e.g., "How many commits are in my repo?")
- **Output**: Structured query object with:
  - `notion_query`: Optimized for Notion search
  - `git_query`: Optimized for GitHub search
  - `query_type`: commit, code, file, issue, repository, general
  - `keywords`: Extracted search terms
  - `is_my_query`: Boolean for user-scoped queries
  - `intent`: Description of user's goal

**Example**:
```
Input: "Show tasks for API v2 and where implemented"
Output: {
  "notion_query": "API v2 tasks",
  "git_query": "API v2 implementation",
  "query_type": "general",
  "keywords": ["API", "v2", "tasks", "implementation"],
  "is_my_query": false,
  "intent": "Find API v2 tasks in Notion and their code implementations"
}
```

**Benefits**:
- Removes filler words ("the", "find", "show")
- Detects query patterns ("my", "count", "how many")
- Constructs platform-specific queries (Notion vs GitHub)

#### 2. AI Correlation (Reasoning)

**Purpose**: Correlate and synthesize information from Notion and GitHub

**Model**: GPT-4o-mini (same model for consistency)

**Usage**:
- **System Prompt**: Instructs the LLM to:
  - Analyze Notion items (pages, databases, content)
  - Analyze GitHub items (commits, code, repositories, issues)
  - Find connections between documentation and code
  - Provide a clear, concise summary
  - Cite sources with confidence scores
- **Input**: 
  - Original user query
  - All Notion items (JSON array)
  - All GitHub items (JSON array)
- **Output**: 
  - Summary explaining correlations
  - Citations with confidence scores (0.0-1.0)

**Example**:
```
Input: 
  Query: "Show tasks for API v2"
  Notion: [{"title": "API v2 Tasks", "content": "Authentication, Payment"}]
  GitHub: [{"path": "src/api/v2/auth.py", "content": "class Auth..."}]

Output: {
  "summary": "Found 2 tasks in Notion for API v2. Authentication task 
              is implemented in src/api/v2/auth.py. Payment task 
              implementation not found.",
  "citations": [
    {"source": "notion", "title": "API v2 Tasks", "confidence": 0.9},
    {"source": "git", "title": "src/api/v2/auth.py", "confidence": 0.85}
  ]
}
```

**Benefits**:
- Understands semantic relationships (not just keyword matching)
- Provides contextual explanations
- Assigns confidence scores based on relevance
- Handles mismatches and gaps gracefully

### How the Agent Determines Relevance Between Notion and Git Data

The agent uses a **two-stage relevance determination** approach:

#### Stage 1: Keyword-Based Matching (Fallback)

If OpenAI correlation fails, the agent uses keyword overlap scoring:

**Algorithm** (`backend/agent/reasoning.py` → `score()`):
```python
def score(item):
    query_words = set(query.lower().split())
    item_text = (item["title"] + " " + item["content"]).lower()
    item_words = set(item_text.split())
    overlap = len(query_words.intersection(item_words))
    return overlap / len(query_words)  # 0.0 to 1.0
```

**Process**:
1. Extract keywords from user query
2. For each Notion/Git item, extract text from title, content, path
3. Calculate word overlap ratio
4. Sort items by score (highest first)
5. Generate citations with confidence = 0.3 + (score * 0.5)

**Limitations**:
- Only matches exact words
- No semantic understanding
- May miss relevant items with different terminology

#### Stage 2: AI-Powered Semantic Correlation (Primary)

The primary method uses OpenAI to understand semantic relationships:

**Process**:

1. **Context Building**:
   - Combines all Notion items into a single context
   - Combines all GitHub items into a single context
   - Includes original user query

2. **Semantic Analysis**:
   - LLM analyzes:
     - **Conceptual matches**: "authentication" in Notion ↔ "auth.py" in GitHub
     - **Temporal relationships**: "API v2 tasks" in Notion ↔ "v2/" directory in GitHub
     - **Functional relationships**: "Payment flow" in Notion ↔ "payment_service.py" in GitHub
   - Understands synonyms and related terms:
     - "user login" ↔ "authentication"
     - "payment" ↔ "billing" ↔ "transaction"

3. **Relevance Scoring**:
   - LLM assigns confidence scores based on:
     - **Exact matches**: High confidence (0.8-1.0)
     - **Semantic matches**: Medium confidence (0.5-0.8)
     - **Weak connections**: Low confidence (0.3-0.5)
   - Considers multiple factors:
     - Keyword overlap
     - Semantic similarity
     - Contextual relevance
     - Completeness of information

4. **Correlation Output**:
   - Identifies which Notion items relate to which GitHub items
   - Explains the relationship in natural language
   - Highlights gaps (documented but not implemented, or vice versa)

**Example**:
```
Notion: "API v2 Authentication Flow: 1. Login 2. JWT validation 3. Session"
GitHub: File "src/api/v2/auth.py" with function "authenticate()"

AI Correlation:
- Matches "Authentication" → "auth.py" (semantic match)
- Matches "Login" → "authenticate()" function (functional match)
- Confidence: 0.9 (high - clear relationship)
```

### Biggest Technical Challenge and Approach

#### Challenge: GitHub Commit Search Accuracy for "My" Queries

**Problem**: 
When users asked "How many commits are in my GitHub repo?" or "Show my last commit", the agent was:
1. Returning commits from other repositories (not the user's)
2. Using `search_code` which doesn't search commit messages
3. Getting incorrect commit counts (360 instead of 25)

**Root Causes**:

1. **No User Scoping**: `search_code` was searching all public repositories, not just the authenticated user's
2. **Wrong Tool Selection**: `search_code` searches code content, not commit messages
3. **Incorrect Response Parsing**: GitHub API responses had different formats that weren't being handled correctly

#### Approach: Multi-Layered Solution

##### Step 1: User Authentication and Scoping

**Solution**: Always get authenticated user first, then scope all searches

```python
# Get user info
user_result = await session.call_tool("get_me", {})
username = user_data.get("login")  # e.g., "premdwivedi"

# Scope all searches to user's repositories
search_code("user:premdwivedi keywords")
search_repositories("user:premdwivedi")
search_issues("user:premdwivedi")
```

**Result**: All searches now limited to authenticated user's repositories

##### Step 2: Commit-Specific Tool Selection

**Solution**: Prioritize `list_commits` for commit-related queries

```python
# Detect commit queries
is_commit_query = any(word in query.lower() for word in ["commit", "committed"])

if is_commit_query:
    # Use list_commits instead of search_code
    # First: Find user's repositories
    repos = await search_repositories("user:premdwivedi")
    # Then: List commits from each repo
    for repo in repos:
        commits = await list_commits(owner=repo.owner, repo=repo.name)
```

**Result**: Commit queries now use the correct tool

##### Step 3: Repository Discovery and Owner Extraction

**Challenge**: GitHub MCP `list_commits` requires `owner` and `repo` parameters, but repository objects had inconsistent structures

**Solution**: Multi-fallback owner extraction

```python
# Try multiple methods to extract owner
owner = None
if isinstance(repo.get("owner"), dict):
    owner = repo.get("owner", {}).get("login", "")
elif repo.get("owner"):
    owner = str(repo.get("owner"))
else:
    # Fallback: Extract from full_name
    full_name = repo.get("full_name", "")  # "premdwivedi/PixSolve"
    if full_name and "/" in full_name:
        owner = full_name.split("/")[0]
    # Final fallback: Use authenticated username
    if not owner and username:
        owner = username
```

**Result**: Owner extraction now works with all repository response formats

##### Step 4: Response Format Handling

**Challenge**: GitHub API responses varied in structure:
- Sometimes: `{"items": [...]}`
- Sometimes: `{"data": [...]}`
- Sometimes: `{"commits": [...]}`
- Sometimes: Direct array `[...]`

**Solution**: Flexible parsing with multiple fallbacks

```python
commits_data = json.loads(response_text)
if isinstance(commits_data, list):
    commits_list = commits_data
elif isinstance(commits_data, dict):
    commits_list = commits_data.get("items", 
                     commits_data.get("data", 
                       commits_data.get("commits", [])))
```

**Result**: Handles all response formats correctly

##### Step 5: Commit Count Aggregation

**Challenge**: For "how many commits" queries, need to count across multiple repositories

**Solution**: Aggregate counts from all user repositories

```python
total_commits_count = 0
for repo in repos_to_check:
    commits = await list_commits(owner=repo.owner, repo=repo.name)
    repo_commit_count = len(commits)
    total_commits_count += repo_commit_count

return {
    "total_count": total_commits_count,
    "repos": [...],
    "summary": f"Found {total_commits_count} commits across {len(repos)} repositories"
}
```

**Result**: Accurate commit counts across all repositories

#### Outcome

The solution successfully:
- ✅ Scopes all searches to authenticated user's repositories
- ✅ Uses correct tools for commit queries (`list_commits` instead of `search_code`)
- ✅ Extracts owner information from various repository formats
- ✅ Parses diverse GitHub API response formats
- ✅ Aggregates commit counts accurately across multiple repositories

**Example Result**:
```
Query: "How many commits are there in my GitHub repo?"
Response: "Found 25 commits across 3 repositories"
  - premdwivedi/PixSolve: 15 commits
  - premdwivedi/my-portfolio: 7 commits
  - premdwivedi/fullstackintern: 3 commits
```

#### Key Learnings

1. **MCP Server Limitations**: Not all tools work for all use cases - need to select the right tool
2. **API Response Variations**: Always handle multiple response formats with fallbacks
3. **User Scoping**: Critical to authenticate and scope searches to avoid retrieving irrelevant data
4. **Iterative Debugging**: Added extensive logging to trace exact API calls and responses
5. **NLP Preprocessing**: Using OpenAI to parse queries helps detect query intent and optimize tool selection

---

## Conclusion

The MCP Agent successfully demonstrates:
- **Modular Architecture**: Clean separation between MCP client, reasoning, and UI
- **Intelligent Query Processing**: NLP-powered query optimization
- **Multi-Source Integration**: Seamless connection to Notion and GitHub via MCP
- **AI-Powered Correlation**: Semantic understanding of relationships between documentation and code
- **Robust Error Handling**: Fallbacks at every stage ensure reliability

The system provides a practical bridge between documentation and code, enabling teams to quickly find connections, verify implementations, and maintain traceability.

