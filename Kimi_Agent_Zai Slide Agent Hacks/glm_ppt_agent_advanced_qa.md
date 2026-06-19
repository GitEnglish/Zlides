# GLM PPT Slide Agent — Deep-Dive Q&A: SDK, Workflows, Editing, PDF Parsing

## Q1: Do I Need the Z.ai SDK to Get All the Juice?

**Short answer: No.** The SDK is a convenience wrapper, not a gatekeeper. Every feature of the slide agent is accessible via raw HTTP POST requests.

### What the SDK Actually Is

Zhipu AI provides two SDK flavors [^76^][^82^]:

| SDK | Install Command | Use Case |
|---|---|---|
| **Legacy** | `pip install zhipuai` | Domestic China platform (`open.bigmodel.cn`) |
| **Modern (Z.ai)** | `pip install zai-sdk` | International platform (`api.z.ai`) |

Both are thin wrappers around `httpx` that handle auth token caching, connection pooling, and type hints [^77^]. They give you a `client.chat.completions.create()` method — but here's the critical thing: **the slide agent does NOT use the chat completions endpoint**.

### The Slide Agent Uses Its Own Endpoint

The `slides_glm_agent` hits a **completely separate endpoint** that is NOT wrapped by the SDK's chat completions interface:

```
POST https://open.bigmodel.cn/api/v1/agents        ← Slide Agent
POST https://open.bigmodel.cn/api/paas/v4/chat/completions  ← SDK's endpoint
```

The SDK's `client.chat.completions.create()` knows nothing about `agent_id`, `conversation_id`, or the SSE stream phases (`thinking`, `tool`, `answer`) that the slide agent uses [^3^]. If you want to use the SDK for the slide agent, you'd need to drop down to its raw HTTP client anyway — at which point you're barely saving any code.

### Raw HTTP vs SDK: Code Comparison

**With SDK (you still need raw HTTP for the agent):**

```python
from zai import ZhipuAiClient
import httpx

client = ZhipuAiClient(api_key="your-key")
# The SDK has NO method for agent_id-based calls
# You must use the internal HTTP client:
response = client._http_client.post(
    "/api/v1/agents",
    json={"agent_id": "slides_glm_agent", ...}
)
```

**With pure `requests` (functionally identical):**

```python
import requests

response = requests.post(
    "https://open.bigmodel.cn/api/v1/agents",
    headers={"Authorization": "Bearer your-key"},
    json={"agent_id": "slides_glm_agent", ...},
    stream=True
)
```

The SDK buys you automatic token refresh and connection reuse — but for a stateful SSE stream that holds a connection open for minutes, connection pooling is irrelevant. You're holding one connection anyway.

### My Recommendation

**Skip the SDK** for the slide agent. Use raw HTTP with `requests` or `httpx`. The API surface is tiny (one POST endpoint, one export endpoint, one history endpoint) and the SSE parsing logic is custom regardless of whether you use the SDK. The only time the SDK makes sense is if you're ALSO doing chat completions, embeddings, or image generation on the same API key — then it pays for itself [^89^].

---

## Q2: Can the Agent Design Its Own Workflows Within the Same Instance, Save Them, and Preview?

**Short answer: No — the agent has no native workflow engine.** But you can build one on top of it using the conversation history API.

### What the Agent CAN Do Natively

The slide agent maintains **conversation state** via `conversation_id`. You can:

- Continue editing across multiple turns
- Add/remove/modify slides
- Request exports at any point
- Query the full conversation history

### The Conversation History API (Workflow Recovery)

This is the key discovery: Zhipu AI provides a **dedicated conversation history endpoint** that works **exclusively with `slides_glm_agent`** [^84^]:

```
POST https://open.bigmodel.cn/api/v1/agents/conversation
```

**Request body:**

```json
{
  "agent_id": "slides_glm_agent",
  "conversation_id": "your-conversation-id",
  "custom_variables": {
    "include_pdf": true,
    "pages": [
      {"position": 1, "width": 1280, "height": 720}
    ]
  }
}
```

**What it returns:** The complete message history of the conversation, including all tool calls (`insert_page`, `remove_slides`, etc.), their inputs, and their HTML outputs. This lets you reconstruct the entire presentation's evolution [^84^].

### Building a Workflow System on Top

The agent cannot design, save, or preview workflows natively — but you can implement this externally:

```python
class SlideWorkflowManager:
    """
    Build workflow snapshots on top of the slide agent's
    conversation history API.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://open.bigmodel.cn/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def capture_workflow_snapshot(self, conversation_id: str) -> dict:
        """
        Capture the full state of a presentation as a 'workflow snapshot'.
        This is your 'save' functionality.
        """
        response = requests.post(
            f"{self.base_url}/agents/conversation",
            headers=self.headers,
            json={
                "agent_id": "slides_glm_agent",
                "conversation_id": conversation_id,
                "custom_variables": {
                    "include_pdf": False,  # Skip export for speed
                    "pages": []  # All pages
                }
            }
        )

        history = response.json()

        # Extract workflow metadata
        snapshot = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "slides": [],
            "edits": []  # Chronological edit log
        }

        for choice in history.get("choices", []):
            for msg in choice.get("message", []):
                for content in msg.get("content", []):
                    if content.get("type") == "object":
                        obj = content.get("object", {})
                        tool_name = obj.get("tool_name")

                        if tool_name == "insert_page":
                            snapshot["slides"].append({
                                "position": obj.get("position"),
                                "title": obj.get("title"),
                                "html_preview": obj.get("output", "")[:500]
                            })
                            snapshot["edits"].append({
                                "type": "insert",
                                "position": obj.get("position"),
                                "description": obj.get("input", "")
                            })

                        elif tool_name == "remove_slides":
                            snapshot["edits"].append({
                                "type": "remove",
                                "positions": obj.get("position", [])
                            })

                        elif tool_name == "modify_page":
                            snapshot["edits"].append({
                                "type": "modify",
                                "position": obj.get("position"),
                                "changes": obj.get("input", "")
                            })

        return snapshot

    def preview_at_edit(self, conversation_id: str, edit_index: int) -> str:
        """
        'Preview' the presentation as it existed after a specific edit.
        Reconstructs HTML by replaying edits up to that point.
        """
        snapshot = self.capture_workflow_snapshot(conversation_id)

        # Replay edits up to the specified index
        current_slides = {}
        for edit in snapshot["edits"][:edit_index + 1]:
            if edit["type"] == "insert":
                for pos in edit.get("position", []):
                    # Fetch the HTML for this slide
                    slide_html = self._get_slide_html(conversation_id, pos)
                    current_slides[pos] = slide_html

            elif edit["type"] == "remove":
                for pos in edit.get("positions", []):
                    current_slides.pop(pos, None)

        # Assemble preview HTML
        return self._assemble_html(current_slides)
```

### The Reality Check

| Feature | Native Support | Workaround |
|---|---|---|
| Multi-turn editing | **Yes** — via `conversation_id` | Built-in |
| Workflow saving | **No** | Use history API + external DB |
| Workflow preview | **No** | Replay edit log from history |
| Branching workflows | **No** | Fork `conversation_id` sessions |
| Agent self-designs workflows | **No** | Orchestrate externally |

**Bottom line:** The agent is a **slide generation engine**, not a workflow orchestrator. For true workflow capabilities (save states, previews, branching, templates), you need to build a layer on top. The conversation history API gives you the raw material; your application provides the workflow semantics.

---

## Q3: Can You Edit Directly on the Output or Add Annotations?

**Short answer: Native editing is limited, but the HTML output makes anything possible.**

### Native Editing Capabilities

The agent provides **three editing primitives** through conversation:

| Operation | Trigger | Tool Used |
|---|---|---|
| **Modify a slide** | "修改第3页" / "change page 3" | `modify_page` (undocumented) [^29^] |
| **Add a slide** | "在第5页后插入新页" | `insert_page` |
| **Delete slides** | "删除第2,4页" | `remove_slides` [^3^] |

These are **text-driven edits** — you describe what you want changed, and the agent regenerates the affected slide(s). There is **no direct manipulation** (no dragging boxes, no WYSIWYG editor, no click-to-edit).

### No Native Annotation System

The slide agent has **no built-in annotation, comment, or批注 (annotation) feature**. Unlike PowerPoint's comment system [^86^] or Google Slides' commenting, the GLM agent output is purely presentational HTML. If you need annotations, you must layer them on top.

### DIY Annotation Layer (HTML Injection)

Since the output is self-contained HTML, you can inject an annotation system:

```html
<!-- Annotation overlay system injected into exported HTML -->
<style>
  .annotation-layer {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: 9999;
  }
  .annotation-marker {
    position: absolute;
    width: 24px; height: 24px;
    background: #e94560;
    border-radius: 50%;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    cursor: pointer;
    pointer-events: auto;
  }
  .annotation-popup {
    position: absolute;
    background: white;
    border: 1px solid #ddd;
    padding: 12px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    max-width: 300px;
    display: none;
  }
  .annotation-popup.active { display: block; }
</style>

<div class="annotation-layer" id="annotation-layer"></div>

<script>
const annotations = [];

function addAnnotation(slideIndex, x, y, text, author) {
  const marker = document.createElement('div');
  marker.className = 'annotation-marker';
  marker.textContent = annotations.length + 1;
  marker.style.left = x + 'px';
  marker.style.top = y + 'px';

  const popup = document.createElement('div');
  popup.className = 'annotation-popup';
  popup.innerHTML = `
    <strong>${author}</strong>
    <p>${text}</p>
    <small>${new Date().toLocaleString()}</small>
  `;

  marker.appendChild(popup);
  marker.onclick = (e) => {
    e.stopPropagation();
    popup.classList.toggle('active');
  };

  document.getElementById('annotation-layer').appendChild(marker);
  annotations.push({slideIndex, x, y, text, author});
}

// Export annotations as JSON for persistence
function exportAnnotations() {
  return JSON.stringify(annotations, null, 2);
}
</script>
```

### Practical Editing Workflow

For your student-focused use case, the best editing approach is a **hybrid system**:

1. **Generate** via the agent (get HTML)
2. **Serve** the HTML in an iframe with your annotation layer injected
3. **Capture** teacher annotations via the overlay
4. **Persist** annotations separately from the slide content
5. **Regenerate** exercises by calling the agent with the original `conversation_id` + modification request

This separation (slides vs. annotations) is actually **better architecture** than native annotations — it lets you update slides without losing annotations, and vice versa.

---

## Q4: Can Layout Parsing Read PDFs I Upload?

**Short answer: Yes — but it's a separate service, not part of the slide agent.**

### The File Parser Service (New)

Zhipu AI launched a **unified file parsing API** [^73^] that is completely separate from the slide agent but uses the same API key. It can parse uploaded PDFs, Word docs, PowerPoints, Excel files, and images — returning structured content with **layout information**.

```
POST https://open.bigmodel.cn/api/paas/v4/files/parser/create
```

### Three Parsing Tiers

| Tier | Supported Formats | Max Size | Output | Price | Best For |
|---|---|---|---|---|---|
| **Prime** | PDF/DOC/DOCX/XLS/XLSX/PPT/PPTX/PNG/JPG/CSV/TXT/MD/HTML + 15 image formats | PDF/DOC ≤100MB, XLS ≤10MB, Images ≤20MB | Images + Markdown + Layout JSON | ¥0.12/page | Complex layouts: academic papers, textbooks, mixed columns, formulas [^73^] |
| **Expert** | PDF only | ≤100MB | Images + Markdown | ¥0.012/page (60% off) | Research papers, financial reports, patents — PDF-optimized [^73^] |
| **Lite** | PDF/DOC/DOCX/XLS/XLSX/PPT/PPTX/PNG/JPG/CSV/TXT/MD | ≤50MB | Plain text only | **Free** (until 2025-10-08) | Quick text extraction, batch preprocessing [^73^] |

### What "Layout Parsing" Actually Returns

The Prime tier returns **three artifacts** per parsed file [^73^]:

1. **Markdown file** — Structured text with headers, tables, lists preserved
2. **Layout JSON** — Detailed bounding box information for every element:
   ```json
   {
     "layout_details": [
       {
         "index": 0,
         "type": "text_block",
         "bbox": [120, 80, 600, 200],
         "content": "Extracted text..."
       },
       {
         "index": 1,
         "type": "table",
         "bbox": [120, 220, 600, 400],
         "rows": 5,
         "columns": 3
       },
       {
         "index": 2,
         "type": "image",
         "bbox": [120, 420, 400, 650],
         "caption": "Figure 1: ..."
       }
     ]
   }
   ```
3. **Visual renderings** — Screenshot images of each parsed page

### Code Example: PDF → Parsed Content → Slide Input

```python
import requests
import time

class PDFToSlidesPipeline:
    """
    Pipeline: Upload PDF → Parse layout → Feed to slide agent
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def parse_pdf(self, pdf_path: str, tier: str = "prime") -> dict:
        """Parse a PDF and return structured content with layout."""

        # Step 1: Create parsing task
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/files/parser/create",
                headers=self.headers,
                files={"file": f},
                data={
                    "tool_type": tier,      # "prime", "expert", or "lite"
                    "file_type": "PDF"
                }
            )

        task_id = response.json()["task_id"]

        # Step 2: Poll for results (async task)
        while True:
            result = requests.get(
                f"https://open.bigmodel.cn/api/paas/v4/files/parser/result/{task_id}/download_link",
                headers=self.headers
            ).json()

            if result.get("status") == "completed":
                break
            time.sleep(2)

        # Step 3: Download parsed content
        markdown_url = result["markdown_url"]      # Markdown output
        layout_url = result["layout_json_url"]     # Layout bounding boxes
        images_url = result["images_url"]          # Page screenshots

        markdown = requests.get(markdown_url).text
        layout = requests.get(layout_url).json()

        return {
            "markdown": markdown,
            "layout": layout,
            "page_count": len(layout.get("pages", []))
        }

    def generate_slides_from_pdf(self, pdf_path: str, prompt_template: str = None) -> dict:
        """
        Full pipeline: Parse PDF → Extract content → Generate slides
        """
        # Parse the PDF
        parsed = self.parse_pdf(pdf_path, tier="prime")

        # Build prompt from parsed content
        content_summary = parsed["markdown"][:8000]  # Truncate for token limits

        slide_prompt = prompt_template or f"""基于以下文档内容，制作一份教学课件PPT：

文档内容：
{content_summary}

要求：
- 提取核心概念和关键知识点
- 保留重要的图表描述（文档共{parsed['page_count']}页）
- 为每页添加思考题
- 风格：教育风，适合课堂投影
"""

        # Send to slide agent
        response = requests.post(
            "https://open.bigmodel.cn/api/v1/agents",
            headers={**self.headers, "Content-Type": "application/json"},
            json={
                "agent_id": "slides_glm_agent",
                "messages": [{"role": "user", "content": [{"type": "text", "text": slide_prompt}]}],
                "stream": True
            },
            stream=True
        )

        return {"stream": response, "parsed_content": parsed}
```

### The GLM-OCR Alternative

For simpler OCR needs (images or short PDFs), there's also the **`glm-ocr` model** [^69^]:

```python
response = client.chat.completions.create(
    model="glm-ocr",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Parse this document"},
            {"type": "file", "file_url": "https://your-pdf-url.pdf"}
        ]
    }],
    extra_body={
        "return_crop_images": True,
        "need_layout_visualization": True  # Returns layout visualization
    }
)
```

The `glm-ocr` model supports PDFs up to **50MB and 100 pages** [^69^], and returns both markdown text and **layout visualization images** showing detected text blocks, tables, and image regions.

### Which Parsing Route to Use?

| Use Case | Service | Why |
|---|---|---|
| Complex academic papers with formulas, multi-column | **File Parser Prime** | Handles complex layouts, returns structured JSON |
| Simple text extraction from PDFs | **File Parser Lite** | Free, fast, good enough |
| Image-based documents (scanned PDFs) | **GLM-OCR model** | Visual model, better at understanding image-based content |
| Batch processing many files | **File Parser Expert** | Cheapest per page, PDF-optimized |

---

## Summary Matrix

| Question | Answer | Key Finding |
|---|---|---|
| **Need SDK?** | **No** — raw HTTP gets everything | SDK doesn't wrap the agent endpoint anyway |
| **Self-designing workflows?** | **No** — build externally | Conversation history API (`/v1/agents/conversation`) gives you the building blocks [^84^] |
| **Direct edit/annotate?** | **Limited native, unlimited via HTML** | `modify_page` tool for edits; inject JS/CSS for annotations |
| **PDF layout parsing?** | **Yes — separate service** | File Parser API with 3 tiers; Prime returns markdown + layout JSON + images [^73^] |
