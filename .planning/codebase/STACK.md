# STACK.md - Technology Stack

**Last Updated:** 2026-03-31

## Runtime

- **Python:** 3.11+ (via `.python-version`)
- **Package Manager:** `uv` (see `pyproject.toml` and `uv.lock`)

## Backend Framework

- **FastAPI:** 0.135.1+ — Web framework for the slide server API
- **Uvicorn:** 0.41.0+ — ASGI server (runs `slide_server.py`)

## Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.135.1+ | Web framework |
| `httpx` | 0.28.1+ | Async HTTP client for Z.AI API calls |
| `neo4j` | 6.1.0+ | **NOT USED** — remove from dependencies |
| `pydantic` | 2.12.5+ | Data validation (ChatRequest model) |
| `pyjwt` | 2.8.0+ | JWT token generation for Z.AI auth |
| `python-dotenv` | 1.2.2+ | Environment variable loading (.env file) |
| `python-multipart` | 0.0.22+ | File upload handling |
| `zhipuai` | 2.1.5+20250825 | Z.AI Python SDK (imported but server uses raw httpx) |

## Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | 9.0.2+ | Test framework |

## Frontend

- **Pure HTML/JS** — No framework
- **html2canvas** — CDN-based, for PNG export
- **Python http.server** — Simple static file server (port 2827)

## External Services

- **Z.AI API** (zhipuai) — Chinese AI service for slide generation
  - Endpoint: `https://api.z.ai/api/v1/agents`
  - Agent: `slides_glm_agent`
  - Auth: JWT tokens signed with HS256

## Configuration

- **Environment:** `.env` file (must contain `Z_AI_API_KEY`)
- **Ports:**
  - Backend: `2828` (FastAPI/uvicorn)
  - Frontend: `2827` (Python http.server)

## Not Used (Remove)

- `neo4j` — Listed in dependencies but **not used anywhere in the codebase**
