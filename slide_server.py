import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import time
import jwt
import json
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Version info
VERSION = "0.1.0"

# Configuration
Z_AI_API_KEY = os.getenv("Z_AI_API_KEY")
ZAI_ENDPOINT = "https://api.z.ai/api/v1/agents"
ZAI_FILES_ENDPOINT = "https://api.z.ai/api/paas/v4/files"
ZAI_CONVERSATION_ENDPOINT = "https://api.z.ai/api/v1/agents/conversation"

# Persistence setup
SAVED_SLIDES_DIR = "saved_slides"
SESSION_FILE = "session.json"
os.makedirs(SAVED_SLIDES_DIR, exist_ok=True)

app = FastAPI(title="Zlides API", version=VERSION)


def get_git_version():
    """Get current git commit hash."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Zlides API",
        "version": VERSION,
        "git_commit": get_git_version()
    }


@app.get("/version")
async def version():
    """Get API version and git commit info."""
    return {
        "version": VERSION,
        "git_commit": get_git_version(),
        "endpoints": {
            "command": "/command",
            "upload": "/upload",
            "history": "/history",
            "style": "/style",
            "pointer": "/pointer"
        }
    }


def generate_token(apikey: str):
    try:
        api_key, secret = apikey.split(".")
    except Exception as e:
        raise Exception("invalid api_key", e)

    payload = {
        "api_key": api_key,
        "exp": int(round(time.time() * 1000)) + 3 * 60 * 1000 + 30 * 1000,
        "timestamp": int(round(time.time() * 1000)),
    }
    ret = jwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"alg": "HS256", "sign_type": "SIGN"},
    )
    return ret


# Allow your frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load existing session if it exists
def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return {"conversation_id": None}


def save_session(session):
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f)


session_store = load_session()


def save_slide_to_file(html: str, prompt: str):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Clean up prompt for filename (remove problematic chars)
        clean_prompt = (
            "".join(c for c in prompt[:30] if c.isalnum() or c in " _-")
            .strip()
            .replace(" ", "_")
        )
        if not clean_prompt:
            clean_prompt = "untitled"
        filename = f"slide_{timestamp}_{clean_prompt}.html"
        filepath = os.path.join(SAVED_SLIDES_DIR, filename)

        # Ensure directory exists
        os.makedirs(SAVED_SLIDES_DIR, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[Save] Slide saved to: {filepath}")
        return filepath
    except Exception as e:
        print(f"[Save Error] Failed to save slide: {e}")
        return f"save_failed: {e}"


class ChatRequest(BaseModel):
    message: str
    system_prompt: str = ""
    page_count: int = 1
    slide_type: str = "slides"  # slides or poster
    layout: str = ""  # title-content, two-column, title-only, blank
    theme: str = ""  # minimal, corporate, creative, dark, colorful
    language: str = "en"  # en, zh-CN, es, fr, de, ja
    web_search: bool = True


@app.post("/command")
async def send_command(request: ChatRequest):
    """
    Receives a text command (e.g., "Create a slide" or "Change color"),
    sends it to Z.AI, and streams the response back to the frontend.
    """
    headers = {
        "Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}",
        "Content-Type": "application/json",
    }

    custom_vars = {}
    if session_store.get("pending_style"):
        custom_vars["style"] = session_store["pending_style"]
    if session_store.get("pending_pointer"):
        custom_vars["pointer"] = session_store["pending_pointer"]

    # Default system prompt that instructs the agent to output HTML slides
    default_system = """You are a professional slide designer. Your task is to generate complete HTML slides.

CRITICAL: Output ONLY valid HTML code. No markdown, no explanations, no conversational text.

Requirements:
1. Return a complete HTML document with <!DOCTYPE html>, <html>, <head>, <body>
2. Use Tailwind CSS via CDN: <script src="https://cdn.tailwindcss.com"></script>
3. Use Material Icons: <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
4. Make it visually professional with good typography, spacing, and colors
5. Include actual content - not placeholder text

The HTML should be a fully self-contained slide ready to display in a browser."""

    messages = []
    if request.system_prompt:
        combined = request.system_prompt + "\n\n" + default_system
        messages.append(
            {"role": "system", "content": [{"type": "text", "text": combined}]}
        )
    else:
        messages.append(
            {"role": "system", "content": [{"type": "text", "text": default_system}]}
        )

    messages.append(
        {"role": "user", "content": [{"type": "text", "text": request.message}]}
    )

    # Start fresh conversation for each slide request to avoid state issues
    # Only reuse conversation_id if explicitly continuing (in future we can add a 'continue' flag)
    conversation_id = session_store.get("conversation_id")

    payload = {
        "agent_id": "slides_glm_agent",
        "stream": True,
        "messages": messages,
    }

    # Only include conversation_id if we have one and message suggests continuation
    if conversation_id and any(
        word in request.message.lower()
        for word in ["edit", "change", "modify", "update", "fix", "adjust"]
    ):
        payload["conversation_id"] = conversation_id
        print(f"[API Request] Continuing conversation: {conversation_id}")
    else:
        print("[API Request] Starting new conversation")
        # Clear old conversation to start fresh
        session_store["conversation_id"] = None

    # Add all slide options
    if request.page_count > 1:
        custom_vars["page_count"] = request.page_count
    if request.slide_type == "poster":
        custom_vars["output_format"] = "poster"
    if request.layout:
        custom_vars["layout"] = request.layout
    if request.theme:
        custom_vars["theme"] = request.theme
    if request.language and request.language != "en":
        custom_vars["language"] = request.language
    if not request.web_search:
        custom_vars["web_search"] = False

    if custom_vars:
        payload["custom_variables"] = custom_vars

    # Add style reference image if available
    style_image_id = session_store.pop("pending_style_image", None)
    if style_image_id:
        payload["file_ids"] = [style_image_id]

    # DEBUG: Print what we're sending
    print(f"[API Request] Agent: {payload['agent_id']}")
    print(f"[API Request] Message: {request.message[:50]}...")
    print(f"[API Request] Custom vars: {custom_vars}")

    async def generate():
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", ZAI_ENDPOINT, json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"[API Error] {response.status_code}: {error_text[:500]}")
                    yield f"data: {json.dumps({'type': 'error', 'text': f'Z.AI API Error: {response.status_code}'})}\n\n"
                    return

                last_data = {}
                accumulated_html = ""
                raw_chunks = []
                html_from_chunks = ""

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if line.startswith("data:"):
                        line_data = line[5:].strip()
                        if line_data == "[DONE]":
                            continue
                        try:
                            if not line_data or line_data.strip() == "[DONE]":
                                continue
                            chunk = json.loads(line_data)

                            # Ensure chunk is a dict before calling .get()
                            if not isinstance(chunk, dict):
                                print(f"[Debug] Skipping non-dict chunk: {type(chunk)}")
                                raw_chunks.append({"raw": str(chunk)[:200]})
                                continue

                            raw_chunks.append(chunk)  # Store for debugging

                            # Check for API errors
                            if chunk.get("status") == "failed":
                                error = chunk.get("error", {})
                                if isinstance(error, dict):
                                    error_msg = error.get("message", "Unknown API error")
                                else:
                                    error_msg = str(error) if error else "Unknown API error"
                                print(f"[API Error] {error_msg}")
                                yield f"data: {json.dumps({'type': 'error', 'text': f'API Error: {error_msg}'})}\n\n"
                                return

                            if "choices" in chunk:
                                last_data = chunk
                                choice = chunk["choices"][0]
                                messages = choice.get("messages", [])

                                # Also try to get HTML from delta if present (newer API format)
                                delta = choice.get("delta", {})
                                if delta:
                                    delta_content = delta.get("content", "")
                                    if (
                                        delta_content
                                        and isinstance(delta_content, str)
                                        and delta_content.strip().startswith("<")
                                    ):
                                        accumulated_html += delta_content

                                for msg in messages:
                                    phase = msg.get("phase", "thinking")
                                    content = msg.get("content", [])

                                    # 1. Handle Text output (Thinking vs Answer) - content can be dict or list
                                    text_content = None
                                    if (
                                        isinstance(content, dict)
                                        and content.get("type") == "text"
                                    ):
                                        text_content = content.get("text", "")
                                    elif isinstance(content, list) and len(content) > 0:
                                        # Check first item
                                        first = content[0]
                                        if (
                                            isinstance(first, dict)
                                            and first.get("type") == "text"
                                        ):
                                            text_content = first.get("text", "")

                                    if text_content:
                                        event_type = (
                                            "answer"
                                            if phase == "answer"
                                            else "thinking"
                                        )
                                        yield f"data: {json.dumps({'type': event_type, 'text': text_content})}\n\n"
                                        # Also accumulate substantial text as potential slide content
                                        if (
                                            len(text_content) > 100
                                            and phase == "answer"
                                        ):
                                            accumulated_html += text_content

                                    # 2. Handle Tool/Object output (for streaming HTML chunks)
                                    elif isinstance(content, list):
                                        for item in content:
                                            if item.get("type") == "object":
                                                obj = item.get("object", {})

                                                # If it's a tool call (like Search), tell the frontend
                                                tool_name = obj.get("tool_name", "")
                                                if tool_name and not obj.get("output"):
                                                    tag = msg.get("tag_en", tool_name)
                                                    input_chunk = obj.get("input", "")
                                                    if input_chunk:
                                                        yield f"data: {json.dumps({'type': 'tool', 'text': input_chunk, 'tool': tag})}\n\n"

                                                # Accumulate HTML from output field
                                                if "output" in obj and isinstance(
                                                    obj["output"], str
                                                ):
                                                    output_str = obj["output"]

                                                    # Unescape the HTML string
                                                    if (
                                                        "\\n" in output_str
                                                        or '\\"' in output_str
                                                    ):
                                                        try:
                                                            output_str = output_str.encode().decode(
                                                                "unicode_escape"
                                                            )
                                                        except (
                                                            UnicodeDecodeError,
                                                            UnicodeEncodeError,
                                                            AttributeError,
                                                        ):
                                                            output_str = (
                                                                output_str.replace(
                                                                    "\\n", "\n"
                                                                )
                                                                .replace('\\"', '"')
                                                                .replace("\\/", "/")
                                                            )

                                                    tool_name_lower = tool_name.lower()

                                                    # Capture any substantial HTML-like content
                                                    is_slide_tool = any(
                                                        kw in tool_name_lower
                                                        for kw in [
                                                            "slide",
                                                            "page",
                                                            "poster",
                                                            "layout",
                                                            "html",
                                                        ]
                                                    )
                                                    is_html = (
                                                        output_str.strip().startswith(
                                                            "<"
                                                        )
                                                        and len(output_str) > 100
                                                    )
                                                    is_large_text = (
                                                        len(output_str) > 500
                                                    )  # Any large text might be content

                                                    if (
                                                        is_html
                                                        or is_slide_tool
                                                        or is_large_text
                                                    ):
                                                        accumulated_html += output_str
                                                        print(
                                                            f"[Accumulate] Added {len(output_str)} chars from {tool_name}"
                                                        )

                                            # Also check for direct text content in list
                                            elif item.get("type") == "text":
                                                text = item.get("text", "")
                                                # If it looks like HTML, accumulate it
                                                if (
                                                    text
                                                    and text.strip().startswith("<")
                                                    and len(text) > 200
                                                ):
                                                    accumulated_html += text
                                                    print(
                                                        f"[Accumulate] Added {len(text)} chars from text item"
                                                    )
                        except Exception as e:
                            print(f"[Debug] SSE parse error: {e}")
                            pass

                # Done reading the stream.
                try:
                    # Log raw response for debugging
                    print(f"[Debug] Total chunks received: {len(raw_chunks)}")

                    # Check if any chunk has HTML directly
                    html_from_chunks = ""
                    for chunk in raw_chunks:
                        try:
                            # Skip if chunk is not a dict
                            if not isinstance(chunk, dict):
                                continue
                            choices = chunk.get("choices", [])
                            for choice in choices:
                                msgs = choice.get("messages", [])
                                for msg in msgs:
                                    content = msg.get("content", {})
                                    # Check for HTML in text content
                                    if (
                                        isinstance(content, dict)
                                        and content.get("type") == "text"
                                    ):
                                        text = content.get("text", "")
                                        if text and (
                                            "<!DOCTYPE" in text
                                            or "<html" in text
                                            or "<div" in text
                                        ):
                                            html_from_chunks = text
                                            print(
                                                f"[Debug] Found HTML in text chunk: {len(text)} chars"
                                            )
                                            break
                                    # Check in list content
                                    elif isinstance(content, list):
                                        for item in content:
                                            if item.get("type") == "text":
                                                text = item.get("text", "")
                                                if text and (
                                                    "<!DOCTYPE" in text
                                                    or "<html" in text
                                                    or "<div" in text
                                                ):
                                                    html_from_chunks = text
                                                    print(
                                                        f"[Debug] Found HTML in list chunk: {len(text)} chars"
                                                    )
                                                    break
                        except (KeyError, TypeError, AttributeError):
                            pass
                        if html_from_chunks:
                            break

                    if html_from_chunks:
                        print(
                            f"[Debug] Using HTML from chunks: {len(html_from_chunks)} chars"
                        )

                    if last_data.get("conversation_id"):
                        session_store["conversation_id"] = last_data["conversation_id"]
                        save_session(session_store)

                    print(f"[Debug] accumulated_html length: {len(accumulated_html)}")
                    print(
                        f"[Debug] html_from_chunks length: {len(html_from_chunks) if html_from_chunks else 0}"
                    )

                    # Priority: 1. HTML from chunks, 2. accumulated, 3. extract from response
                    if html_from_chunks:
                        slide_html = html_from_chunks
                    elif accumulated_html:
                        slide_html = accumulated_html
                    else:
                        slide_html = extract_html_from_response(last_data)

                    print(
                        f"[Debug] slide_html length after extraction: {len(slide_html) if slide_html else 0}"
                    )

                    # Handle case where no HTML was generated
                    if not slide_html or len(slide_html) < 100:
                        # Try to get text content from the last response
                        slide_html = extract_text_as_html(last_data, request.message)
                        print(
                            f"[Debug] After text extraction: {len(slide_html) if slide_html else 0}"
                        )

                    # If still nothing, try to construct from raw chunks
                    if not slide_html or len(slide_html) < 100:
                        # Look through all chunks for any HTML-like content
                        for chunk in reversed(raw_chunks):
                            # Skip if not a dict
                            if not isinstance(chunk, dict):
                                continue
                            choices = chunk.get("choices", [])
                            for choice in choices:
                                msgs = choice.get("messages", [])
                                for msg in msgs:
                                    content = msg.get("content", [])
                                    for item in content:
                                        if item.get("type") == "text":
                                            text = item.get("text", "")
                                            if text and len(text) > 200:
                                                slide_html = wrap_in_slide_html(
                                                    text, request.message
                                                )
                                                print(
                                                    f"[Debug] Found text in chunk: {len(text)} chars"
                                                )
                                                break
                                    if slide_html and len(slide_html) > 100:
                                        break
                                if slide_html and len(slide_html) > 100:
                                    break
                            if slide_html and len(slide_html) > 100:
                                break

                    # Fix double-escaped HTML strings
                    if (
                        "\\n" in slide_html
                        or '\\"' in slide_html
                        or "\\/" in slide_html
                    ):
                        try:
                            # Try to unescape as JSON string
                            slide_html = slide_html.encode().decode("unicode_escape")
                        except Exception:
                            # Fallback to manual replacement
                            slide_html = (
                                slide_html.replace("\\n", "\n")
                                .replace('\\"', '"')
                                .replace("\\/", "/")
                                .replace("\\t", "\t")
                            )

                    style = session_store.pop("pending_style", None)
                    session_store.pop("pending_pointer", None)

                    slide_html = inject_sdk(slide_html, request.message, style)

                    # Save the HTML to a file
                    filepath = save_slide_to_file(slide_html, request.message)

                    final_event = {
                        "type": "final_html",
                        "html": slide_html,
                        "conversation_id": session_store.get("conversation_id"),
                        "saved_to": filepath,
                    }
                    yield f"data: {json.dumps(final_event)}\n\n"

                except Exception as e:
                    import traceback

                    error_msg = f"Server error: {str(e)}\n{traceback.format_exc()}"
                    print(error_msg)
                    yield f"data: {json.dumps({'type': 'error', 'text': f'Failed to process response: {str(e)}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    upload_type: str = "file",  # file, ocr, style
):
    """
    Upload auxiliary files to Z.AI.
    Types:
    - file: General file upload (glossaries, docs)
    - ocr: Extract text from image
    - style: Use as style reference for next generation

    Supports: pdf, doc, xlsx, ppt, txt, jpg, png, webp (max 100MB)
    """
    if not Z_AI_API_KEY:
        raise HTTPException(status_code=401, detail="ZAI_API_KEY not configured")

    allowed_types = {
        "pdf",
        "doc",
        "xlsx",
        "ppt",
        "txt",
        "jpg",
        "jpeg",
        "png",
        "gif",
        "webp",
    }
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in allowed_types:
        raise HTTPException(
            status_code=400, detail=f"File type not allowed. Allowed: {allowed_types}"
        )

    contents = await file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 100MB limit")

    # Upload to Z.AI
    files = {"file": (file.filename, contents, file.content_type)}
    data = {"purpose": "agent"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            ZAI_FILES_ENDPOINT,
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}"},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Z.AI API Error: {response.text}")

    result = response.json()
    file_id = result.get("id")

    # Handle special upload types
    if upload_type == "style" and file_id:
        # Store style reference for next generation
        session_store["pending_style_image"] = file_id
        result["message"] = "Style reference queued for next generation"

    elif upload_type == "ocr" and file_id:
        # Try to extract text via a quick agent call
        try:
            extracted = await extract_text_from_image(file_id)
            result["extracted_text"] = extracted
            result["message"] = f"OCR complete. Extracted {len(extracted)} characters."
        except Exception as e:
            result["extracted_text"] = ""
            result["message"] = f"Image uploaded but OCR failed: {e}"

    return result


async def extract_text_from_image(file_id: str) -> str:
    """Use the agent to extract text from an uploaded image (OCR)."""
    payload = {
        "agent_id": "slides_glm_agent",
        "stream": False,
        "conversation_id": session_store.get("conversation_id"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Extract all text from this image (file ID: {file_id}). Return only the extracted text, no commentary.",
                    }
                ],
            }
        ],
        "file_ids": [file_id],
    }

    headers = {"Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(ZAI_ENDPOINT, json=payload, headers=headers)

    if response.status_code != 200:
        return ""

    data = response.json()
    # Extract text from response
    try:
        choices = data.get("choices", [])
        if choices:
            messages = choices[0].get("messages", [])
            for msg in messages:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            return item.get("text", "")
    except (KeyError, TypeError, AttributeError):
        pass

    return ""


@app.get("/history")
async def get_history():
    """Get conversation history for current session."""
    if not session_store.get("conversation_id"):
        return {"history": [], "conversation_id": None}

    payload = {
        "agent_id": "slides_glm_agent",
        "conversation_id": session_store["conversation_id"],
    }

    headers = {"Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            ZAI_CONVERSATION_ENDPOINT, json=payload, headers=headers
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch history")

    return response.json()


@app.post("/style")
async def ingest_style(request: dict):
    """
    Ingest style reference (URL, color, font, image) without storing.
    Passes to agent in next command via custom_variables.
    """
    style_data = request.get("style", {})
    session_store["pending_style"] = style_data
    return {"status": "style_queued", "style": style_data}


@app.post("/pointer")
async def ingest_pointer(request: dict):
    """
    Ingest a pointer (URL, file reference) without storing.
    Passes to agent in next command via custom_variables.
    """
    pointer_data = request.get("pointer", {})
    session_store["pending_pointer"] = pointer_data
    return {"status": "pointer_queued", "pointer": pointer_data}


@app.post("/sdk")
async def sdk_regenerate(request: dict):
    """
    SDK endpoint: regenerates exercises for hosted slides.
    Works with gitenglish-sdk.js client SDK.
    """
    prompt = request.get("prompt", "")
    zones = request.get("zones", ["exercises"])
    style = request.get("style", None)

    custom_vars = {}
    if style:
        custom_vars["style"] = style

    payload = {
        "agent_id": "slides_glm_agent",
        "stream": True,
        "conversation_id": session_store.get("conversation_id"),
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": f"Generate exercises: {prompt}"}],
            }
        ],
    }
    if custom_vars:
        payload["custom_variables"] = custom_vars

    headers = {"Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}"}
    import json

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST", ZAI_ENDPOINT, json=payload, headers=headers
        ) as response:
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="SDK regeneration failed")

            full_data = ""
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    full_data = line

    data = {}
    if full_data.startswith("data:"):
        try:
            data = json.loads(full_data[5:])
        except (json.JSONDecodeError, Exception):
            pass

    exercises = {}
    for zone in zones:
        exercises[zone] = extract_exercises_from_response(data, zone)

    return {"exercises": exercises, "type": "exercises-regenerated"}


SDK_SCRIPT = '<script src="https://www.gitenglish.com/sdk/gitenglish-sdk.js"></script>'


def wrap_in_slide_html(content: str, title: str = "Slide") -> str:
    """Wrap plain text content in proper HTML slide template."""
    # If it's already HTML, return as-is
    content_stripped = content.strip()
    if content_stripped.startswith("<") and (
        "</" in content_stripped or "/>" in content_stripped
    ):
        return content

    # Convert markdown-style formatting to HTML
    html_content = content
    # Bold
    html_content = html_content.replace("**", "<strong>", 1).replace(
        "**", "</strong>", 1
    )
    # Headers
    lines = html_content.split("\n")
    formatted_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            formatted_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            formatted_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            formatted_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            formatted_lines.append(f"<li>{line[2:]}</li>")
        elif line:
            formatted_lines.append(f"<p>{line}</p>")

    html_content = "\n".join(formatted_lines)

    # Wrap list items in ul
    html_content = html_content.replace("</li>\n<li>", "</li>\n<li>")
    if "<li>" in html_content and "<ul>" not in html_content:
        html_content = html_content.replace("<li>", "<ul>\n<li>", 1)
        html_content = html_content.replace("</li>\n<p>", "</li>\n</ul>\n<p>")
        if not html_content.endswith("</ul>"):
            html_content += "\n</ul>"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 40px;
            max-width: 1200px;
            margin: 0 auto;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ font-size: 2.5em; margin-bottom: 20px; color: #1a1a1a; }}
        h2 {{ font-size: 2em; margin: 30px 0 15px; color: #2a2a2a; }}
        h3 {{ font-size: 1.5em; margin: 25px 0 10px; color: #3a3a3a; }}
        p {{ margin-bottom: 15px; font-size: 1.1em; }}
        ul {{ margin: 20px 0; padding-left: 30px; }}
        li {{ margin-bottom: 10px; font-size: 1.1em; }}
        strong {{ color: #1a1a1a; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


def inject_sdk(html: str, prompt: str = "", style: dict = None) -> str:
    """Inject GitEnglish SDK into generated HTML."""
    # First ensure it's proper HTML
    html = wrap_in_slide_html(html, "Generated Slide")

    meta_tags = f'<meta name="ai-prompt" content="{prompt}">'
    if style:
        meta_tags += f'\n<meta name="ai-style" content="{style}">'
    if "</head>" in html:
        return html.replace("</head>", f"{meta_tags}{SDK_SCRIPT}</head>")
    if "<body" in html:
        return html.replace("<body", f"{meta_tags}{SDK_SCRIPT}<body")
    return f"{meta_tags}{SDK_SCRIPT}{html}"


def extract_html_from_response(data):
    """
    Parses the Z.AI response to find the 'output' HTML.
    Handles SSE streaming format and various response structures.
    """
    try:
        import json

        # Handle SSE format (data: {...})
        if isinstance(data, str) and data.startswith("data:"):
            lines = data.strip().split("\n")
            for line in reversed(lines):
                if line.startswith("data:"):
                    try:
                        chunk = json.loads(line[5:])
                        if "choices" in chunk:
                            data = chunk
                            break
                    except (json.JSONDecodeError, Exception):
                        continue

        # Ensure data is a dict before calling .get()
        if not isinstance(data, dict):
            print(f"[Extract] Warning: data is not a dict, it's {type(data)}")
            return ""

        choices = data.get("choices", [])
        if not choices:
            return ""

        # Try multiple response structures
        messages = choices[0].get("messages", [])

        # Structure 1: messages[].content[].object.output (original)
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "object":
                        obj = item.get("object", {})
                        if "output" in obj:
                            output = obj["output"]
                            if (
                                output and len(output) > 50
                            ):  # Make sure it's substantial
                                return output

        # Structure 2: messages[].content.text (direct text)
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        if text and len(text) > 50:
                            return text

        # Structure 3: message.content as dict
        for msg in messages:
            content = msg.get("content", {})
            if isinstance(content, dict):
                text = content.get("text", "")
                if text and len(text) > 50:
                    return text

        return ""

    except Exception as e:
        print(f"[Extract Error] {e}")
        return ""


def extract_text_as_html(data, title: str = "Slide") -> str:
    """Extract text content from response and convert to HTML."""
    try:
        if not isinstance(data, dict):
            print(f"[Extract Text] Warning: data is not a dict, it's {type(data)}")
            return ""
        choices = data.get("choices", [])
        if not choices:
            return ""

        messages = choices[0].get("messages", [])
        all_text = []

        for msg in messages:
            content = msg.get("content", [])

            # Handle content as dict (e.g., {"type": "text", "text": "..."})
            if isinstance(content, dict):
                if content.get("type") == "text":
                    text = content.get("text", "")
                    if text and len(text) > 10:  # Ignore tiny fragments
                        all_text.append(text)

            # Handle content as list (e.g., [{"type": "text", ...}])
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text = item.get("text", "")
                            if text and len(text) > 10:
                                all_text.append(text)
                        # Also check for object with output
                        elif item.get("type") == "object":
                            obj = item.get("object", {})
                            output = obj.get("output", "")
                            if output and isinstance(output, str) and len(output) > 50:
                                return output  # Return raw HTML output directly

        combined_text = "\n\n".join(all_text)
        if combined_text and len(combined_text) > 50:
            print(f"[Extract] Found {len(combined_text)} chars of text")
            return wrap_in_slide_html(combined_text, title)

        return ""
    except Exception as e:
        print(f"[Extract Error] {e}")
        return ""


def extract_exercises_from_response(data, zone: str = "exercises"):
    """Extract exercises from Z.AI response for SDK."""
    try:
        if not isinstance(data, dict):
            return {}
        choices = data.get("choices", [])
        if not choices:
            return {}

        # Use 'messages' (list) not 'message' (dict)
        messages = choices[0].get("messages", [])
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "object":
                        obj = item.get("object", {})
                        output = obj.get("output", "")
                        if output:
                            return parse_exercises_html(output, zone)

        return {}
    except Exception:
        return {}


def parse_exercises_html(html: str, zone: str) -> dict:
    """Parse exercises from HTML - simple implementation."""
    exercises = {}
    import re

    questions = re.findall(r'<p class="ge-text">(.*?)</p>', html, re.DOTALL)
    options = re.findall(r'<input type="radio"[^>]*>([^<]+)', html)
    correct = re.findall(r'data-correct="([^"]+)"', html)

    for i, q in enumerate(questions):
        qid = f"q{i + 1}"
        exercises[qid] = {
            "text": q.strip(),
            "options": [o.strip() for o in options[i * 4 : (i + 1) * 4]]
            if options
            else [],
            "correct": correct[i] if i < len(correct) else "",
        }

    return exercises


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8766)
