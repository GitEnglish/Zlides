import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import os
import time
import jwt
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

VERSION = "0.2.0"
Z_AI_API_KEY = os.getenv("Z_AI_API_KEY")
ZAI_ENDPOINT = "https://api.z.ai/api/v1/agents"
ZAI_FILES_ENDPOINT = "https://api.z.ai/api/paas/v4/files"
SAVED_SLIDES_DIR = "saved_slides"
SESSION_FILE = "session.json"
STYLE_BANK_DIR = Path("style_bank")
ASSETS_DIR = Path("assets")

os.makedirs(SAVED_SLIDES_DIR, exist_ok=True)
os.makedirs(STYLE_BANK_DIR, exist_ok=True)

app = FastAPI(title="Zlides API", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Formats & Styles ─────────────────────────────────────────────────────────

FORMATS = {
    "slides": "Create a multi-slide HTML presentation. Use <section> tags for each slide with page-break-after CSS. Include a title slide, content slides, and a closing slide as appropriate.",
    "poster": "Create a single-page HTML poster. Everything visible on one screen/page. Eye-catching, visual, information-dense.",
    "worksheet": "Create an HTML worksheet with exercises, fill-in-the-blank, matching, or short answer sections. Include numbered exercises with clear instructions. Use HTML form elements (input, checkbox) for interactive fields but NO <script> tags — any interactivity must be CSS-only.",
    "report": "Create an HTML document/report. Structured with headings, paragraphs, lists, and tables as needed. Professional document layout suitable for printing.",
    "rr": "Create an HTML learning resource. Where content can be regenerated (exercises, example sentences, vocabulary lists, practice questions), place <button id='regenerate' data-prompt='SPECIFIC regeneration instruction here'> with a clear label. Do NOT put regenerate buttons on static content like instructions or explanations — only where it makes pedagogical sense to generate new variants.",
}


def load_style_bank():
    """Load all style packs from style_bank/ directory."""
    styles = {}
    for f in STYLE_BANK_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            styles[data["id"]] = data
        except Exception as e:
            print(f"[StyleBank] Failed to load {f}: {e}")
    return styles


def build_system_prompt(fmt: str, style_id: str, language: str = "en") -> str:
    """Build the system prompt from format + style selections."""

    format_instruction = FORMATS.get(fmt, FORMATS["slides"])

    # GLM slides agent already knows how to create slides - just guide the format
    base = f"Create a {fmt} (HTML format).\n\n{format_instruction}"

    # Load style hint if specified
    if style_id and style_id != "auto":
        styles = load_style_bank()
        style = styles.get(style_id)
        if style:
            base += (
                f"\n\nStyle: {style.get('prompt_hint', style.get('name', style_id))}"
            )

    return base


def clean_agent_output(raw: str) -> str:
    """Clean the raw agent output — strip code fences, extract HTML."""
    if not raw or len(raw) < 20:
        return ""

    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        # Remove opening fence
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1 :]
        # Remove closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    text = text.strip()

    # If it starts with HTML, we're good
    if text.startswith("<") or text.startswith("<!DOCTYPE"):
        return text

    # Try to find HTML content within the text
    # Look for <!DOCTYPE or <html or <div as start markers
    for marker in ["<!DOCTYPE", "<html", "<div", "<section", "<style"]:
        idx = text.find(marker)
        if idx >= 0:
            return text[idx:]

    return ""


# ── Helpers ──────────────────────────────────────────────────────────────────


def get_git_version():
    try:
        import subprocess

        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def generate_token(apikey: str):
    api_key, secret = apikey.split(".", 1)
    payload = {
        "api_key": api_key,
        "exp": int(round(time.time() * 1000)) + 10 * 60 * 1000,
        "timestamp": int(round(time.time() * 1000)),
    }
    return jwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"alg": "HS256", "sign_type": "SIGN"},
    )


SESSION_TTL_SECONDS = 30 * 60


def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                ts = data.get("updated_at", 0)
                if ts and (time.time() - ts) > SESSION_TTL_SECONDS:
                    return {"conversation_id": None}
                return data
        except Exception:
            pass
    return {"conversation_id": None}


def save_session(session):
    session["updated_at"] = time.time()
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f)


session_store = load_session()


def save_slide_to_file(html: str, prompt: str):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean = (
            "".join(c for c in prompt[:30] if c.isalnum() or c in " _-")
            .strip()
            .replace(" ", "_")
        )
        if not clean:
            clean = "untitled"
        filepath = os.path.join(SAVED_SLIDES_DIR, f"slide_{timestamp}_{clean}.html")
        os.makedirs(SAVED_SLIDES_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[Save] {filepath}")
        return filepath
    except Exception as e:
        return f"save_failed: {e}"


def wrap_in_slide_html(content: str, title: str = "Slide") -> str:
    content_stripped = content.strip()
    if content_stripped.startswith("<") and (
        "</" in content_stripped or "/>" in content_stripped
    ):
        return content

    lines = content.split("\n")
    formatted = []
    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            formatted.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            formatted.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            formatted.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            formatted.append(f"<li>{line[2:]}</li>")
        elif line:
            formatted.append(f"<p>{line}</p>")

    html_content = "\n".join(formatted)
    if "<li>" in html_content and "<ul>" not in html_content:
        html_content = html_content.replace("<li>", "<ul>\n<li>", 1)
        html_content = html_content.replace("</li>\n<p>", "</li>\n</ul>\n<p>")
        if not html_content.endswith("</ul>"):
            html_content += "\n</ul>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       padding: 40px; max-width: 1200px; margin: 0 auto; line-height: 1.6; color: #333; }}
h1 {{ font-size: 2.5em; margin-bottom: 20px; }}
h2 {{ font-size: 2em; margin: 30px 0 15px; }}
h3 {{ font-size: 1.5em; margin: 25px 0 10px; }}
p {{ margin-bottom: 15px; font-size: 1.1em; }}
ul {{ margin: 20px 0; padding-left: 30px; }}
li {{ margin-bottom: 10px; font-size: 1.1em; }}
</style></head>
<body>{html_content}</body></html>"""


def combine_tool_pages(pages: list) -> str:
    """Combine HTML chunks from tool outputs into a single document.

    The GLM slides agent streams HTML in ~100 char chunks via tool calls.
    We need to concatenate them in order to form the complete document.
    """
    if not pages:
        return ""

    # Sort by position if available, otherwise preserve insertion order
    sorted_pages = sorted(
        pages,
        key=lambda p: (
            p.get("position", [0, 0])[0] if p.get("position") else 0,
            p.get("position", [0, 0])[1]
            if p.get("position") and len(p.get("position", [])) > 1
            else 0,
        ),
    )

    # Concatenate all HTML chunks in order
    html_chunks = [p["html"] for p in sorted_pages]
    combined = "".join(html_chunks)

    # Decode escaped newlines and quotes from the API response
    combined = combined.replace("\\n", "\n").replace('\\"', '"')

    # Clean up: ensure we have valid HTML
    combined = combined.strip()

    # If the combined text looks like HTML, return it
    if combined.startswith("<") or combined.startswith("<!DOCTYPE"):
        return combined

    # Otherwise try to extract HTML from within
    for marker in ["<!DOCTYPE", "<html", "<div", "<section", "<style"]:
        idx = combined.find(marker)
        if idx >= 0:
            return combined[idx:]

    return ""


def extract_final_html(data: dict) -> str:
    """Extract HTML from a complete (non-streaming) API response."""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices", [])
    if not choices:
        return ""

    messages = choices[0].get("messages", [])

    # Priority 1: object output (the agent's primary HTML output)
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "object":
                    output = item.get("object", {}).get("output", "")
                    if output and len(output) > 50:
                        return output

    # Priority 2: text content that looks like HTML
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    if text and ("<" in text) and len(text) > 50:
                        cleaned = clean_agent_output(text)
                        if cleaned:
                            return cleaned

    # Priority 3: dict content
    for msg in messages:
        content = msg.get("content", {})
        if isinstance(content, dict):
            text = content.get("text", "")
            if text and len(text) > 50:
                return text

    return ""


# ── Request Models ───────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    system_prompt: str = ""
    page_count: int | None = None
    slide_type: str = "slides"
    layout: str = ""
    theme: str = ""
    language: str = "en"
    web_search: bool = True
    format: str = "slides"
    style: str = "auto"


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Zlides API",
        "version": VERSION,
        "git_commit": get_git_version(),
    }


@app.get("/version")
async def version():
    return {"version": VERSION, "git_commit": get_git_version()}


@app.get("/formats")
async def list_formats():
    """List available formats."""
    return [{"id": k, "description": v[:80]} for k, v in FORMATS.items()]


# ── Style Bank Endpoints ─────────────────────────────────────────────────────


@app.get("/styles")
async def list_styles():
    """List all styles in bank (metadata only)."""
    styles = load_style_bank()
    result = []
    for sid, s in styles.items():
        result.append(
            {
                "id": sid,
                "name": s.get("name", sid),
                "preview_colors": s.get("preview_colors", []),
                "brand_png": s.get("brand_png"),
            }
        )
    # Always include "auto" as an option
    return [{"id": "auto", "name": "Auto", "preview_colors": []}] + result


@app.get("/styles/{style_id}")
async def get_style(style_id: str):
    """Get full style pack."""
    styles = load_style_bank()
    if style_id not in styles:
        raise HTTPException(status_code=404, detail="Style not found")
    return styles[style_id]


@app.post("/styles/save")
async def save_style(request: dict):
    """Save a style pack to the bank."""
    style = request.get("style")
    if not style or not isinstance(style, dict) or "id" not in style:
        raise HTTPException(status_code=400, detail="Style must have an 'id'")

    sid = style["id"].lower().replace(" ", "-")
    filepath = STYLE_BANK_DIR / f"{sid}.json"

    style["id"] = sid
    style.setdefault("created_at", datetime.now().strftime("%Y-%m-%d"))
    style.setdefault("prompt_hint", "")
    style.setdefault("css", {})
    style.setdefault("fonts", {})
    style.setdefault("print_css", "")

    filepath.write_text(
        json.dumps(style, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"saved": True, "id": sid}


@app.delete("/styles/{style_id}")
async def delete_style(style_id: str):
    """Delete a style from the bank."""
    filepath = STYLE_BANK_DIR / f"{style_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Style not found")
    filepath.unlink()
    return {"deleted": True, "id": style_id}


# ── Export Endpoints ─────────────────────────────────────────────────────────


@app.post("/export/html")
async def export_html(request: dict):
    """Return full HTML document for download."""
    html = request.get("html", "")
    if not html:
        raise HTTPException(status_code=400, detail="No HTML provided")
    return JSONResponse(content={"html": html})


# ── Saved Slides Endpoints ──────────────────────────────────────────────────


@app.get("/saved")
async def list_saved_slides():
    """List all saved slides with metadata."""
    saved_dir = Path(SAVED_SLIDES_DIR)
    slides = []
    for f in sorted(saved_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            content = f.read_text(encoding="utf-8")
            title = f.stem
            m = __import__("re").search(r"<title>(.*?)</title>", content)
            if m:
                title = m.group(1)
            slides.append({
                "filename": f.name,
                "title": title,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%b %d, %H:%M"),
            })
        except Exception:
            pass
    return slides


@app.get("/saved/{filename}")
async def get_saved_slide(filename: str):
    """Serve a saved slide HTML file."""
    filepath = Path(SAVED_SLIDES_DIR) / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Slide not found")
    return FileResponse(filepath)


# ── Main Generation Endpoint ─────────────────────────────────────────────────


@app.post("/command")
async def send_command(request: ChatRequest):
    headers = {
        "Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en",
    }

    # Build system prompt from format + style
    system_prompt = build_system_prompt(
        fmt=request.format or request.slide_type or "slides",
        style_id=request.style or request.theme or "auto",
        language=request.language,
    )

    # Page count instruction
    page_instruction = ""
    effective_page_count = request.page_count or 5
    page_instruction = f"\nCreate exactly {effective_page_count} {'slides' if request.format == 'slides' else 'sections'}."
    if request.layout:
        page_instruction += f" Layout preference: {request.layout}."

    user_text = request.message
    if request.system_prompt:
        user_text = f"{request.system_prompt}\n\n{user_text}"

    full_prompt = f"{system_prompt}{page_instruction}\n\nUSER REQUEST:\n{user_text}"

    messages = [{"role": "user", "content": [{"type": "text", "text": full_prompt}]}]
    conversation_id = session_store.get("conversation_id")

    payload = {
        "agent_id": "slides_glm_agent",
        "stream": True,
        "messages": messages,
        "enable_thinking": True,
    }

    if request.web_search:
        payload["tools"] = [{"type": "web_search", "web_search": {"enable": True}}]

    payload["max_pages"] = effective_page_count

    # Safe max_tokens to prevent context-length crashes (cap at 1/3 of 200k context)
    payload["max_tokens"] = 65000

    # Layout whitespace control (ctrl_step): 0.7 = good balance of readability and richness
    payload["ctrl_step"] = 0.7

    # Determine if this is an edit request
    is_edit_request = conversation_id and any(
        word in request.message.lower()
        for word in [
            "edit",
            "change",
            "modify",
            "update",
            "fix",
            "adjust",
            "reformat",
            "layout",
        ]
    )

    # Add optimizations: cache salting, preserved thinking, strict JSON, tool streaming
    import secrets
    import uuid

    payload["extra_body"] = {
        "cache_salt": secrets.token_urlsafe(32),
        "thinking": {
            "type": "disabled" if is_edit_request else "enabled",
            "clear_thinking": False,
        },
        "tool_stream": True,
    }
    payload["response_format"] = {"type": "json_object"}
    payload["requestId"] = str(uuid.uuid4())

    # Continue conversation on edit requests
    if is_edit_request:
        payload["conversation_id"] = conversation_id
    else:
        session_store["conversation_id"] = None

    # Inject any queued style image
    style_image_id = session_store.pop("pending_style_image", None)
    if style_image_id:
        payload["file_ids"] = [style_image_id]

    pending_style = session_store.pop("pending_style", None)
    if pending_style:
        style_instruction = f"\n\nStyle Reference: {json.dumps(pending_style)}"
        messages[0]["content"][0]["text"] += style_instruction

    pending_pointer = session_store.pop("pending_pointer", None)
    if pending_pointer:
        pointer_instruction = f"\n\nReference URL: {json.dumps(pending_pointer)}"
        messages[0]["content"][0]["text"] += pointer_instruction

    print(
        f"[API] Format: {request.format} | Style: {request.style} | Message: {request.message[:50]}..."
    )

    async def generate():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST", ZAI_ENDPOINT, json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'type': 'error', 'text': f'Z.AI API Error: {response.status_code}'})}\n\n"
                    return

                all_chunks = []
                answer_texts = []
                tool_html_pages = []  # HTML from insert_page/tool outputs
                last_valid_chunk = {}

                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data:"):
                        continue

                    line_data = line[5:].strip()
                    if line_data == "[DONE]":
                        continue

                    try:
                        chunk = json.loads(line_data)
                        if not isinstance(chunk, dict):
                            continue

                        all_chunks.append(chunk)

                        if chunk.get("status") == "failed":
                            error = chunk.get("error", {})
                            error_msg = (
                                error.get("message", "Unknown")
                                if isinstance(error, dict)
                                else str(error)
                            )
                            yield f"data: {json.dumps({'type': 'error', 'text': f'API Error: {error_msg}'})}\n\n"
                            return

                        if (
                            "choices" in chunk
                            and isinstance(chunk["choices"], list)
                            and chunk["choices"]
                        ):
                            last_valid_chunk = chunk
                            choice = chunk["choices"][0]
                            if not isinstance(choice, dict):
                                continue

                            # Handle both streaming (messages list) and final (message field)
                            msgs = choice.get("messages", [])
                            if not msgs:
                                single_msg = choice.get("message")
                                if single_msg:
                                    msgs = (
                                        single_msg
                                        if isinstance(single_msg, list)
                                        else [single_msg]
                                    )

                            for msg in msgs:
                                if not isinstance(msg, dict):
                                    continue
                                phase = msg.get("phase", "thinking")
                                content = msg.get("content", [])

                                # content can be a single dict or a list
                                content_items = []
                                if isinstance(content, dict):
                                    content_items = [content]
                                elif isinstance(content, list):
                                    content_items = content
                                else:
                                    continue

                                for item in content_items:
                                    if not isinstance(item, dict):
                                        continue

                                    item_type = item.get("type", "")

                                    # ── type "object": tool calls with HTML output ──
                                    if item_type == "object":
                                        obj = item.get("object", {})
                                        if isinstance(obj, dict):
                                            tool_name = obj.get("tool_name", "")
                                            output = obj.get("output", "")
                                            position = obj.get("position", [])

                                            if not tool_name:
                                                continue

                                            # Decode escaped characters from API response
                                            if output and isinstance(output, str):
                                                output = output.replace(
                                                    "\\n", "\n"
                                                ).replace('\\"', '"')

                                            print(f"[Stream] Got tool output: {tool_name}, {len(output) if output else 0} chars, position={position}")

                                            if tool_name == "insert_page":
                                                if output and isinstance(output, str) and len(output) > 10:
                                                    tool_html_pages.append(
                                                        {
                                                            "tool": tool_name,
                                                            "html": output,
                                                            "position": position,
                                                        }
                                                    )
                                                    yield f"data: {json.dumps({'type': 'slide_page', 'tool': tool_name, 'html': output, 'position': position})}\n\n"

                                            elif tool_name == "remove_slides":
                                                yield f"data: {json.dumps({'type': 'slide_remove', 'tool': tool_name, 'positions': position})}\n\n"

                                            elif tool_name == "modify_page":
                                                if output and isinstance(output, str) and len(output) > 10:
                                                    # Try to replace in our local tracking list if possible
                                                    # Using slide_state might be better but we need tool_html_pages to combine at the end.
                                                    replaced = False
                                                    for i, p in enumerate(tool_html_pages):
                                                        if p.get("position") and p["position"][0] == position[0]:
                                                            tool_html_pages[i] = {
                                                                "tool": tool_name,
                                                                "html": output,
                                                                "position": position,
                                                            }
                                                            replaced = True
                                                            break
                                                    if not replaced:
                                                        tool_html_pages.append({
                                                            "tool": tool_name,
                                                            "html": output,
                                                            "position": position,
                                                        })
                                                    yield f"data: {json.dumps({'type': 'slide_replace', 'tool': tool_name, 'html': output, 'position': position})}\n\n"

                                            elif tool_name == "access_page":
                                                yield f"data: {json.dumps({'type': 'slide_navigate', 'tool': tool_name, 'position': position})}\n\n"

                                            elif tool_name == "search":
                                                # Just send it as thinking info
                                                if output:
                                                    safe_output = output[:100] if output else ''
                                                    thinking_data = {'type': 'thinking', 'text': f'\n[Searching: {safe_output}...]\n'}
                                                    yield f"data: {json.dumps(thinking_data)}\n\n"

                                        continue

                                    # ── type "text": thinking/answer text ──
                                    if item_type == "text":
                                        text_content = item.get("text", "")
                                        if text_content:
                                            event_type = (
                                                "answer"
                                                if phase == "answer"
                                                else "thinking"
                                            )
                                            yield f"data: {json.dumps({'type': event_type, 'text': text_content})}\n\n"
                                            if (
                                                phase == "answer"
                                                and len(text_content) > 50
                                            ):
                                                answer_texts.append(text_content)

                    except Exception as e:
                        print(f"[Parse] SSE error: {e}")

                # Debug: log what we received
                print(
                    f"[DEBUG] Received {len(all_chunks)} chunks, {len(tool_html_pages)} tool HTML pages, {len(answer_texts)} answer texts"
                )

                # ── Build final HTML ──
                try:
                    slide_html = ""

                    # Best: combine all tool HTML pages into one document
                    if tool_html_pages:
                        slide_html = combine_tool_pages(tool_html_pages)
                        print(
                            f"[DEBUG] combine_tool_pages returned: {len(slide_html)} chars from {len(tool_html_pages)} pages"
                        )

                    # Next: extract from the last complete response chunk (non-streaming style)
                    if not slide_html and last_valid_chunk:
                        slide_html = extract_final_html(last_valid_chunk)
                        print(
                            f"[DEBUG] extract_final_html returned: {len(slide_html)} chars"
                        )

                    # Next: concatenate all answer-phase texts and clean
                    if not slide_html and answer_texts:
                        combined = "\n".join(answer_texts)
                        slide_html = clean_agent_output(combined)

                    # Fallback: try every chunk from end to start for tool outputs
                    if not slide_html:
                        for c in reversed(all_chunks):
                            slide_html = extract_final_html(c)
                            if slide_html:
                                break

                    # Last resort: wrap plain text
                    if not slide_html or len(slide_html) < 50:
                        plain = " ".join(answer_texts) if answer_texts else ""
                        if plain and len(plain) > 30:
                            slide_html = wrap_in_slide_html(plain, request.message)
                        else:
                            slide_html = wrap_in_slide_html(
                                "No slide content generated. Try a different prompt.",
                                request.message,
                            )

                    # Save conversation_id only for edit requests (continuations)
                    if is_edit_request and last_valid_chunk.get("conversation_id"):
                        session_store["conversation_id"] = last_valid_chunk[
                            "conversation_id"
                        ]
                        save_session(session_store)

                    # Append print CSS from style bank if applicable
                    style_id = request.style or request.theme or "auto"
                    if style_id and style_id != "auto":
                        styles = load_style_bank()
                        sp = styles.get(style_id)
                        if sp and sp.get("print_css"):
                            print_css = sp["print_css"]
                            if "</head>" in slide_html:
                                slide_html = slide_html.replace(
                                    "</head>", f"<style>{print_css}</style>\n</head>"
                                )
                            elif "</style>" in slide_html:
                                slide_html = slide_html.replace(
                                    "</style>", f"\n{print_css}\n</style>"
                                )

                    filepath = save_slide_to_file(slide_html, request.message)

                    yield f"data: {json.dumps({'type': 'final_html', 'html': slide_html, 'saved_to': filepath})}\n\n"

                except Exception as e:
                    import traceback

                    print(f"[Error] {traceback.format_exc()}")
                    yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")




# ── Async & Export ────────────────────────────────────────────────────────────

@app.post("/async")
async def async_generate(request: ChatRequest):
    if not Z_AI_API_KEY:
        raise HTTPException(status_code=401, detail="Z_AI_API_KEY not configured")

    token = generate_token(Z_AI_API_KEY, exp_seconds=3600)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = "https://api.z.ai/v1/agents/async-result"

    payload = {
        "agent_id": "slides_glm_agent",
        "custom_variables": {
            "include_pdf": False
        }
    }
    # Basic fire and forget async job
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/export/pdf")
async def export_pdf(request: dict):
    if not Z_AI_API_KEY:
        raise HTTPException(status_code=401, detail="Z_AI_API_KEY not configured")

    conversation_id = request.get("conversation_id")
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id required")

    token = generate_token(Z_AI_API_KEY, exp_seconds=3600)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = "https://api.z.ai/v1/agents/conversation"

    payload = {
        "agent_id": "slides_glm_agent",
        "conversation_id": conversation_id,
        "custom_variables": {
            "include_pdf": True
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            data = response.json()
            # In a real app we'd parse the PDF link from data, but we'll return the whole data block
            # or try to extract it depending on Z.AI's response format
            return {"status": "success", "data": data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))



# ── Conversation History ──────────────────────────────────────────────────────

@app.get("/conversation/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    if not Z_AI_API_KEY:
        raise HTTPException(status_code=401, detail="Z_AI_API_KEY not configured")

    token = generate_token(Z_AI_API_KEY, exp_seconds=3600)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = "https://api.z.ai/v1/agents/conversation"

    payload = {
        "agent_id": "slides_glm_agent",
        "conversation_id": conversation_id,
        "custom_variables": {
            "include_pdf": True
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), upload_type: str = "file"):
    if not Z_AI_API_KEY:
        raise HTTPException(status_code=401, detail="Z_AI_API_KEY not configured")

    allowed = {"pdf", "doc", "xlsx", "ppt", "txt", "jpg", "jpeg", "png", "gif", "webp"}
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        raise HTTPException(
            status_code=400, detail=f"File type not allowed. Allowed: {allowed}"
        )

    contents = await file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 100MB limit")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            ZAI_FILES_ENDPOINT,
            files={"file": (file.filename, contents, file.content_type)},
            data={"purpose": "agent"},
            headers={
                "Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}",
                "Accept-Language": "en-US,en",
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Z.AI API Error: {response.text}")

    result = response.json()
    if upload_type == "style" and result.get("id"):
        session_store["pending_style_image"] = result["id"]
        result["message"] = "Style reference queued for next generation"

    return result


@app.post("/style")
async def ingest_style(request: dict):
    session_store["pending_style"] = request.get("style", {})
    return {"status": "style_queued", "style": session_store["pending_style"]}


@app.post("/pointer")
async def ingest_pointer(request: dict):
    session_store["pending_pointer"] = request.get("pointer", {})
    return {"status": "pointer_queued", "pointer": session_store["pending_pointer"]}


app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


if __name__ == "__main__":
    import uvicorn
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 2828))
    sock.close()

    uvicorn.run(app, host="0.0.0.0", port=2828)
