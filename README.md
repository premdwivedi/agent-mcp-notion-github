# MCP Agent - Notion & GitHub Integration

Intelligent agent that connects to Notion and GitHub via MCP (Model Context Protocol) servers to provide contextual answers by cross-referencing documentation and code.

## Features

- **Notion Integration**: Search and query Notion pages, databases, and content
- **GitHub Integration**: Access repositories, commits, code, and issues via GitHub API
- **AI Reasoning**: Uses OpenAI to correlate information and provide intelligent answers
- **Modern Stack**: Django + React + Inertia.js with TypeScript

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (optional)
- OpenAI API Key
- GitHub Personal Access Token (for GitHub integration)
- Notion Internal Integration Token (for Notion integration)

### Local Development

1. **Clone and setup environment**:
```bash
cp .env_example .env
# Edit .env with your API keys
```

2. **Backend setup**:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

3. **Frontend setup**:
```bash
cd frontend
npm install
npm run build
```

4. **Access**: Open http://localhost:8000

### Docker Setup

```bash
docker compose up --build
```

Then open http://localhost:8000

## Configuration

Create a `.env` file in the project root:

```env
# OpenAI API Key (required)
OPENAI_API_KEY=sk-your-key-here

# Notion MCP Server
NOTION_MCP_CMD=python agent/notion_mcp_server.py --token ntn_your_notion_token
NOTION_TOKEN=ntn_your_notion_token

# GitHub MCP Server (uses Docker)
GIT_MCP_CMD=docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token ghcr.io/github/github-mcp-server
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token

# Optional: Notion root page IDs (comma-separated)
NOTION_ROOT_IDS=

# Django Settings
DEBUG=true
SECRET_KEY=your-secret-key-here
```

### Getting API Keys

**OpenAI API Key**:
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy and add to `.env`

**GitHub Personal Access Token**:
1. Go to https://github.com/settings/tokens
2. Generate new token (classic) with `repo` scope
3. Copy token (starts with `ghp_`) and add to `.env`

**Notion Internal Integration Token**:
1. Go to https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the token (starts with `ntn_`) and add to `.env`
4. Share your Notion pages/databases with the integration

## Project Structure

```
backend/
  ├── agent/          # MCP client, reasoning, and Notion MCP server
  ├── api/            # REST API endpoints
  ├── core/           # Django settings
  └── web/            # Inertia views

frontend/
  ├── src/
  │   └── pages/     # React components
  └── dist/          # Built assets
```

## API Endpoints

- `GET /` - Chat interface
- `GET /api/health/mcp` - MCP server health check
- `POST /api/agent/query` - Query agent with natural language

## How It Works

1. **Query Parsing**: Uses OpenAI to parse natural language queries and extract optimized search terms
2. **MCP Integration**: Connects to Notion and GitHub MCP servers via stdio
3. **Data Retrieval**: Searches Notion pages and GitHub repositories simultaneously
4. **AI Correlation**: Uses OpenAI to correlate results and provide contextual answers with citations
5. **Response**: Returns summary with source citations

## Troubleshooting

**MCP servers not connecting**:
- Check health endpoint: `curl http://localhost:8000/api/health/mcp`
- Verify environment variables in `.env`
- Check Docker is running (for GitHub MCP server)
- Review backend logs for connection errors

**Notion authentication**:
- Ensure `NOTION_TOKEN` is set correctly
- Verify integration has access to your Notion pages
- Check token format (should start with `ntn_`)

**GitHub authentication**:
- Verify `GITHUB_PERSONAL_ACCESS_TOKEN` is valid
- Ensure token has `repo` scope
- Check Docker socket is mounted (for Docker setup)

## Development

**Frontend development**:
```bash
cd frontend
npm run dev  # Vite dev server on separate port
```

**Backend development**:
```bash
cd backend
python manage.py runserver
```

**Run tests**:
```bash
cd backend
python manage.py test
```

## License

See LICENSE file for details.
