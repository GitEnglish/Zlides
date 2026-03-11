# Zlides: Headless Slide Editor

## Project Overview
Zlides is a **Headless Slide Editor** that leverages the Z.AI Agent as its "engine." It consists of a FastAPI backend that proxies commands to the Z.AI API and a simple HTML/JS frontend that provides a live preview and chat interface for commanding slide edits.

### Key Technologies
- **Backend**: Python (FastAPI, httpx, uvicorn)
- **Frontend**: Vanilla HTML, CSS, and JavaScript
- **API Integration**: Z.AI Agents API (`slides_glm_agent`)
- **Package Management**: `uv`

---

## Building and Running

### Prerequisites
- Python 3.11 or higher
- `uv` installed
- A valid `ZAI_API_KEY` environment variable

### Setting up the environment
```bash
# Initialize and sync dependencies
uv sync
```

### Running the Backend
```bash
# Start the FastAPI server
uv run python slide_server.py
```
The server will start at `http://0.0.0.0:8000`.

### Running the Frontend
Simply open `index.html` in your web browser. It connects to the backend at `http://localhost:8000/command`.

---

## Architecture: "The Slide Sandbox"
1.  **Frontend (`index.html`)**: 
    - Left side: Chat Input for commanding the Z.AI Agent.
    - Right side: Live Preview (iframe) that renders the HTML output from the agent in real-time.
2.  **Backend (`slide_server.py`)**: 
    - A proxy that handles `ZAI_API_KEY` and manages the `conversation_id` to maintain session context.
    - Saves the `conversation_id` from Z.AI responses to ensure subsequent edit commands (e.g., "Make the font bigger") apply to the same slide.

---

## Key Files
- `slide_server.py`: The FastAPI server implementation.
- `index.html`: The visual dashboard and editor UI.
- `pyproject.toml` / `uv.lock`: Dependency and project configuration.
- `requirements.txt`: Legacy requirement list (for reference).

---

## Development Conventions
- **Session Management**: Always reuse the `conversation_id` from the `session_store` in `slide_server.py` to keep the agent's memory intact.
- **HTML Extraction**: The backend includes logic in `extract_html_from_response` to parse the nested Z.AI response structure.
- **CORS**: The server currently allows all origins (`*`) for easy local development.
