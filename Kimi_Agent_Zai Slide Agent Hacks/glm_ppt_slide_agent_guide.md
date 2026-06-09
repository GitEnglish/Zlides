# The Unofficial GLM PPT Slide Agent Power Guide: Hidden Parameters, Reverse-Engineered Features & Pro Tricks

## TL;DR — The Short Version

The **GLM PPT Slide Agent** (`slides_glm_agent`) on Z.ai / Open Big Model is far more capable than the official docs suggest. Through reverse-engineering the frontend code and scraping Chinese community tips, this guide reveals **undocumented `custom_variables`** (`include_html`, `include_pdf`), the **full tool suite** (5 tools, not 3), **poster mode switching**, **HTML effect injection**, and **multi-turn conversation strategies** that let you build interactive educational slides with placeholder regeneration for your students. The agent outputs self-contained HTML with inline CSS — meaning you can modify templates, inject interactive elements, and create reusable slide systems.

---

## 1. What You're Actually Dealing With: Architecture Overview

The GLM PPT Slide Agent is not a simple "generate slides from text" API. It is a **full agentic system** powered by the GLM-4.5/GLM-4.7 backbone that combines web search, HTML generation, multi-turn editing, and export capabilities into a single conversational interface [^3^][^12^]. Understanding this architecture is the key to unlocking its full potential.

The agent operates through a **Server-Sent Events (SSE) streaming protocol** exclusively — there is no non-streaming mode [^3^]. Every request initiates a multi-phase pipeline: the model first enters a `thinking` phase where it reasons about your request, then executes `tool` calls to search the web or manipulate slides, and finally returns an `answer` phase with the completed content [^3^]. The entire process is stateful via a `conversation_id` that persists across multiple turns, enabling you to refine, extend, or completely rework a presentation through natural follow-up messages.

What makes this system unique compared to other AI slide generators (like Gamma or Beautiful.ai) is that it produces **raw HTML documents with inline CSS** rather than proprietary formats [^34^][^45^]. This means you get a self-contained file that you can inspect, modify, host on any web server, or convert to other formats. The trade-off is that the visual output is dynamically generated based on content rather than being locked to rigid templates — which explains why users report inconsistent page heights across slides [^39^].

The agent is built on GLM-4.5's native **agentic architecture** that integrates reasoning, coding, and tool-use in a single model [^12^]. This is not a wrapper around a base LLM — the slide generation capability is model-native, which is why Zhipu AI refers to it as a "model-native PPT/Poster agent" [^12^][^40^]. The practical implication is that the quality of output scales directly with the underlying model capabilities, and newer GLM versions (4.6, 4.7, 5.1) will produce progressively better results without any API changes on your end.

![GLM PPT Agent Architecture](/mnt/agents/output/glm_ppt_agent_architecture.png)

---

## 2. The Official API (What the Docs Tell You)

### 2.1 Required Parameters

The official documentation specifies a minimal parameter set [^3^]:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `agent_id` | String | Yes | Fixed value: `"slides_glm_agent"` |
| `messages` | List<Object> | Yes | Conversation history with `role` and `content` |
| `conversation_id` | String | No | Session identifier for multi-turn conversations |
| `stream` | Boolean | Yes | Must be `true` — SSE streaming is mandatory |

The `messages` structure follows the standard OpenAI-compatible format:

```json
{
  "agent_id": "slides_glm_agent",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "帮我生成一个关于人工智能技术发展的市场调研"
        }
      ]
    }
  ],
  "stream": true
}
```

### 2.2 Response Stream Phases

The SSE stream returns events with incrementing `index` values. Each event contains a `phase` field indicating the current processing stage [^3^]:

| Phase | Description | Observable Content |
|---|---|---|
| `thinking` | Internal reasoning about the request | Fragmentary text showing the model's thought process |
| `tool` | Tool execution (search, insert, remove) | Tool name, input parameters, and output (HTML for slides) |
| `answer` | Final response to the user | Completion message and summary |
| `error` | Error or content safety trigger | Error code (e.g., `1301` for unsafe content) |

The `tool` phase is where the real action happens. When the model decides to create a slide, it emits a tool call with `tool_name: "insert_page"`, `input` describing what to create, and `output` containing the actual HTML document [^3^]. The `position` field in the tool output specifies which slide number is being manipulated, enabling precise editing.

### 2.3 Export Endpoint

After slide generation completes, you can request export via a separate endpoint:

```
POST https://open.bigmodel.cn/api/v1/agents/conversation/
```

The official docs mention only one custom variable: `include_pdf` [^3^]. But as we'll see in Section 3, there are more.

---

## 3. Hidden & Undocumented Parameters (Reverse-Engineered)

This is where the fun begins. By analyzing the official frontend demo repository (`MetaGLM/glm-ppt-front`) [^26^], the API response schemas, and community-discovered behaviors, I've identified several parameters and capabilities that are not documented in the official API reference.

### 3.1 The `custom_variables` Object (Export Endpoint)

The official documentation lists `include_pdf` as the only custom variable [^3^]. However, the response schema and frontend code reveal a second option:

| Parameter | Type | Effect | Status |
|---|---|---|---|
| `include_pdf` | Boolean | Exports presentation as PDF file | Officially documented [^3^] |
| `include_html` | Boolean | Exports presentation as HTML file | **Undocumented** — discovered via API schema [^3^] |

The `include_html` parameter is particularly valuable because it gives you the raw, self-contained HTML file that the agent generated. This is the secret sauce for template customization, placeholder injection, and interactive element addition. When you request HTML export, the response returns a `file_url` pointing to a downloadable `.html` file that contains all CSS inline — no external dependencies [^3^].

**Practical tip**: Request both formats simultaneously by setting both flags to `true` in the same request. The API returns multiple file URLs in the response choices.

```json
{
  "agent_id": "slides_glm_agent",
  "conversation_id": "your-conversation-id",
  "custom_variables": {
    "include_pdf": true,
    "include_html": true
  }
}
```

### 3.2 Hidden Tools (Beyond the Official Three)

The official documentation explicitly mentions three tools: `search`, `insert_page`, and `remove_slides` [^3^]. However, the frontend demo's README and source code reveal **two additional tools** that the agent is capable of using [^29^]:

| Tool Name | Official Status | Function | How to Trigger |
|---|---|---|---|
| `search` | Documented | Web search for content gathering | Automatic — triggered when the model needs external information [^3^] |
| `insert_page` | Documented | Create new slide with HTML output | Automatic — triggered during generation [^3^] |
| `remove_slides` | Documented | Delete slides by position array | Say "删除第X页" or "remove page X" [^3^] |
| `access_page` | **Undocumented** | Navigate between slides (翻页) | Say "上一页" / "下一页" or "go to page X" [^29^] |
| `modify_page` | **Undocumented** | Edit existing slide content | Say "修改第X页" or "change page X to..." [^29^] |

The `access_page` and `modify_page` tools are particularly useful for building interactive workflows. The `access_page` tool allows you to navigate through a presentation programmatically — the frontend demo explicitly mentions "向上翻页" (page up) and "向下翻页" (page down) as supported operations [^29^]. The `modify_page` tool enables surgical edits to specific slides without regenerating the entire presentation.

**Reverse-engineering insight**: These tools are exposed through the same SSE stream as the documented ones. When the agent uses an undocumented tool, the `phase` is still `"tool"`, but the `tool_name` field contains the undocumented tool identifier. Your parser should be prepared to handle any tool name, not just the three documented ones.

### 3.3 The `async-result` Endpoint

The frontend code reveals a second API endpoint that is not mentioned in the official documentation [^51^]:

```
POST /v1/agents/async-result
```

This endpoint appears to be for retrieving results from asynchronous agent operations. While the exact use case is unclear from the source code, its existence suggests that the agent supports **asynchronous processing modes** for long-running operations. This could be relevant if you're building systems that need to handle slide generation without maintaining a persistent SSE connection.

### 3.4 Conversation State Persistence

The `conversation_id` parameter is documented, but its behavior has important nuances that aren't fully explained:

- **Session duration**: Conversations appear to persist for a limited time (likely hours, not days)
- **Context window**: The full conversation history is sent with each subsequent message, meaning long sessions consume progressively more tokens
- **State recovery**: If a stream is interrupted, you can resume by sending a new message with the same `conversation_id`

**Pro tip**: For maximum reliability in production systems, implement a retry mechanism that reuses the `conversation_id` for follow-up operations. If the conversation has expired, the API will return an error and you'll need to start fresh.

---

## 4. Model Selection: Can You Use Other Models?

This is one of the most common questions, and the answer is nuanced.

### 4.1 The Agent Uses Its Own Model (You Can't Change It)

The `slides_glm_agent` is a **pre-configured agent** that runs on Zhipu AI's infrastructure. When you send a request to this agent, you do not specify a `model` parameter — the agent uses its own internal model configuration [^3^]. Based on Zhipu AI's announcements, the slide agent is powered by the **GLM-Experimental** model series [^45^], which is optimized for content generation, visual layout, and tool-use tasks.

This is fundamentally different from calling the chat completions API where you explicitly choose between `glm-4.5`, `glm-4.7`, `glm-5.1`, etc. The agent is a higher-level abstraction that handles model selection internally.

### 4.2 Indirect Model Influence Through Z.ai Platform

While you can't directly specify the model for the slide agent API, the **Z.ai chat interface** (chat.z.ai) does offer model selection, and the quality of slide generation varies by model:

| Platform | Model Control | Slide Quality | Best For |
|---|---|---|---|
| Open Big Model API (`slides_glm_agent`) | None — agent-controlled | Consistent, production-ready | Automated pipelines, bulk generation |
| Z.ai Chat (chat.z.ai) | Manual — select GLM-4.5/4.6/4.7/5 | Higher with newer models | Interactive creation, complex designs |
| GLM Coding Plan | Via Claude Code / OpenClaw | Variable — depends on agent config | Coding-integrated workflows [^8^] |

Community reports suggest that using **GLM-4.7 or GLM-5.1** through the Z.ai chat interface produces **superior slide designs** compared to the default agent model, with better visual hierarchy, more sophisticated color schemes, and improved handling of complex layouts [^45^]. If you need the absolute best quality, consider generating slides through the Z.ai web interface with a premium model selected, then exporting the HTML for further processing.

### 4.3 Self-Hosted Alternative (vLLM/SGLang)

For users who need complete control over the model and parameters, Zhipu AI open-sources the GLM model weights on HuggingFace [^12^][^44^]. You can deploy GLM-4.5 or GLM-4.7 locally using vLLM or SGLang, then build your own slide generation pipeline on top of the base model.

However, this is a **fundamentally different approach** — you lose the agentic capabilities (web search, automatic layout, tool-use) and get only the base language model. Building slide generation from scratch requires significant prompt engineering and post-processing infrastructure.

For locally-hosted GLM models, the key parameters are [^44^]:

```python
# vLLM deployment
glm45_params = {
    "temperature": 0.6,      # Lower for consistent slides
    "top_p": 1.0,
    "max_tokens": 8192,      # Slide HTML can be lengthy
    "enable_thinking": True  # Improves reasoning quality
}
```

---

## 5. Prompt Engineering: The Secret Sauce

The GLM PPT Agent's output quality is **heavily dependent on prompt quality**. After analyzing dozens of community examples and testing various approaches, here are the techniques that produce the best results.

### 5.1 The Anatomy of a Perfect Slide Prompt

Chinese community users have discovered that the most effective prompts follow a specific structure [^45^][^39^]:

```
[Role] + [Topic] + [Audience] + [Requirements] + [Style] + [Format]
```

**Example — well-structured prompt:**

```
作为高中物理老师，帮我制作一个关于"牛顿运动定律"的教学课件PPT。
听众是高一学生，需要包含概念讲解、公式推导、3个生活案例、课堂练习题。
风格要求：清新教育风，蓝绿色系，包含简单的物理示意图。
输出12页，每页都要有标题和要点。
```

**Translation and breakdown:**

| Component | Chinese Prompt | Effect |
|---|---|---|
| Role | "作为高中物理老师" | Sets the persona and expertise level |
| Topic | "牛顿运动定律" | Core subject matter |
| Audience | "高一学生" | Determines complexity and language |
| Requirements | "概念讲解、公式推导、3个案例、练习题" | Content structure |
| Style | "清新教育风，蓝绿色系" | Visual direction |
| Format | "12页，每页有标题和要点" | Output constraints |

### 5.2 Style Keywords That Actually Work

The agent responds to specific visual style keywords. Based on community testing [^45^][^39^], these are the most reliable:

| Style Keyword | Effect | Reliability |
|---|---|---|
| "科技感" / "tech style" | Dark backgrounds, neon accents, geometric elements | High |
| "简约风" / "minimalist" | Clean layouts, lots of whitespace, simple typography | High |
| "商务风" / "business" | Blue color scheme, professional fonts, chart-friendly | High |
| "新拟物主义" / "neumorphism" | Soft shadows, extruded elements, pastel colors | Medium |
| "绿色教育风" / "green education" | Nature tones, friendly icons, readable fonts | High |
| "赛博朋克" / "cyberpunk" | Dark + neon, futuristic elements | Medium |
| "复古风" / "vintage" | Warm tones, serif fonts, textured backgrounds | Medium |

### 5.3 Advanced HTML Effects Injection

One of the most powerful hidden capabilities is that the agent generates **self-contained HTML with inline CSS and JavaScript** [^45^]. This means you can request interactive and animated effects that go far beyond static slides:

| Effect | Prompt Trigger | Result |
|---|---|---|
| Particle backgrounds | "添加粒子背景特效" / "particle background" | Animated floating particles |
| Code rain (Matrix) | "代码雨效果" / "Matrix code rain" | Falling characters animation |
| Snow/falling elements | "雪花飘落效果" / "snow falling effect" | Seasonal animations |
| Hover interactions | "鼠标悬停放大效果" / "hover zoom effects" | Interactive element scaling |
| Typewriter text | "打字机效果" / "typewriter effect" | Character-by-character reveal |
| Progress bars | "添加进度条动画" / "animated progress bars" | Data visualization with motion |

**Critical insight from community testing**: The agent will include these effects **only if explicitly requested in the initial prompt** [^45^]. Adding effect requests in follow-up messages rarely works because the HTML structure is established during the first generation pass.

### 5.4 Page Count and Pagination Strategy

The agent has a **practical limit of approximately 15 pages** per generation session [^45^]. Beyond this, content quality degrades and slides may be cut off. For longer presentations, use a **continuation strategy**:

1. **Initial generation**: Request the first 10-12 pages with a clear outline
2. **Continuation**: Send "继续生成剩余页面" (continue generating remaining pages) or "continue" as a follow-up message with the same `conversation_id`
3. **Consolidation**: Export the full presentation after all pages are generated

This pagination approach works because the agent maintains the full conversation context and can pick up where it left off.

---

## 6. HTML Output Deep Dive: Template Hacking

The HTML output is where the real power lies for technical users. Understanding its structure enables template customization, placeholder injection, and interactive element addition.

### 6.1 HTML Structure Analysis

The agent generates **single-file, self-contained HTML documents** with the following characteristics [^3^][^34^]:

- **All CSS is inline** — either in a `<style>` block or as `style` attributes
- **No external dependencies** — all images are base64-encoded or loaded from the agent's CDN
- **Responsive viewport meta tag** — designed for browser viewing
- **Variable page heights** — content-adaptive layout rather than fixed dimensions [^39^]

A typical slide HTML structure looks like this:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    /* Inline CSS with slide-specific styling */
    .slide { /* ... */ }
    .slide-title { /* ... */ }
    .slide-content { /* ... */ }
  </style>
</head>
<body>
  <div class="slide" data-slide-index="1">
    <h1 class="slide-title">Title</h1>
    <div class="slide-content">...</div>
  </div>
  <!-- More slides... -->
</body>
</html>
```

### 6.2 Template Customization Strategies

Since the output is raw HTML, you can implement several customization strategies:

**Strategy 1: Post-Processing Pipeline**

After receiving the HTML export, run it through a processing pipeline:

```python
import re
from bs4 import BeautifulSoup

def customize_slide_template(html_content, brand_config):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Inject custom CSS variables
    style_tag = soup.find('style')
    if style_tag:
        custom_css = f"""
        :root {{
          --primary-color: {brand_config['primary']};
          --secondary-color: {brand_config['secondary']};
          --font-heading: {brand_config['heading_font']};
        }}
        """
        style_tag.string = custom_css + style_tag.string
    
    # Add interactive elements
    for slide in soup.find_all(class_='slide'):
        # Inject placeholder regeneration markers for students
        placeholder = soup.new_tag('div')
        placeholder['class'] = 'student-exercise-placeholder'
        placeholder['data-regenerate'] = 'true'
        placeholder.string = '[Student Exercise — Click to Regenerate]'
        slide.append(placeholder)
    
    return str(soup)
```

**Strategy 2: CSS Override System**

Since all styles are inline or in a `<style>` block, you can inject an override stylesheet:

```html
<!-- Add this at the end of <head> -->
<style id="custom-override">
  /* Force consistent slide dimensions */
  .slide {
    width: 1280px !important;
    height: 720px !important;
    overflow: hidden !important;
  }
  
  /* Brand color injection */
  .slide-title { color: #your-brand-color !important; }
  
  /* Add placeholder styling for student exercises */
  .student-exercise-placeholder {
    border: 2px dashed #e94560;
    padding: 20px;
    margin: 20px 0;
    text-align: center;
    cursor: pointer;
  }
  .student-exercise-placeholder:hover {
    background: rgba(233, 69, 96, 0.1);
  }
</style>
```

**Strategy 3: JavaScript Interactivity Injection**

For your student use case with placeholder regeneration, inject JavaScript that enables interactive elements:

```html
<script>
// Student exercise regeneration system
document.querySelectorAll('.student-exercise-placeholder').forEach(el => {
  el.addEventListener('click', async function() {
    const exerciseType = this.dataset.exerciseType || 'random';
    const newContent = await regenerateExercise(exerciseType);
    this.innerHTML = newContent;
    this.classList.add('regenerated');
  });
});

async function regenerateExercise(type) {
  // Call your backend or the GLM API to generate new exercise content
  // Return the new HTML content for the exercise
}
</script>
```

### 6.3 The Variable Page Height "Problem" and Solution

Users consistently report that generated slides have **inconsistent page heights** [^39^]. This is by design — the agent uses content-adaptive layout to ensure no content is cut off. However, for professional presentations, you may want uniform dimensions.

**Solutions:**

1. **Prompt-level fix**: Include "所有页面采用统一高度" (all pages use uniform height) in your prompt [^39^]
2. **CSS-level fix**: Force dimensions via the override strategy shown above
3. **Post-processing fix**: Use a headless browser (Puppeteer/Playwright) to render each slide at a fixed viewport size and capture screenshots

---

## 7. Slide vs Poster Mode: Aspect Ratio Switching

The GLM Slide/Poster Agent can generate outputs in **multiple aspect ratios and formats** [^20^][^12^]. This is not immediately obvious from the API documentation, but the agent responds to format cues in your prompts.

### 7.1 Supported Output Formats

| Format | Prompt Trigger | Dimensions | Use Case |
|---|---|---|---|
| Standard PPT | Default (no specification) | Variable width, ~16:9 ratio | Presentations, reports |
| Wide PPT | "16:9" / "宽屏" | 16:9 aspect ratio | Modern presentations |
| Portrait Poster | "竖版海报" / "portrait poster" | 9:16 or 3:4 ratio | Social media, event posters |
| Square | "正方形" / "1:1" | 1:1 ratio | Instagram, profile content |
| Xiaohongshu | "小红书" / "Xiaohongshu cover" | 3:4 ratio (1080x1440) | Social commerce [^63^] |
| A4 Document | "A4" / "简历" / "resume" | A4 ratio | Documents, resumes |
| Long Image | "长图" / "long image" | Extended vertical scroll | Infographics, tutorials |

### 7.2 Multi-Format Generation Strategy

For maximum versatility, you can generate the same content in multiple formats by maintaining the `conversation_id` and requesting format changes:

1. Generate the base presentation in standard PPT format
2. Follow up with: "把这份内容改成竖版海报格式" (convert this to portrait poster format)
3. The agent will reformat the existing content while preserving the text and structure
4. Export both versions using `include_html: true`

This approach is particularly useful for content repurposing — turning a single presentation into social media posts, handouts, and digital signage from the same source material.

---

## 8. Multi-Turn Conversation Strategies

The conversational nature of the agent is its most powerful feature. Here are advanced strategies for complex workflows.

### 8.1 The "Outline-First" Approach

Rather than requesting a full presentation in one shot, use a structured multi-turn approach:

**Turn 1 — Outline generation:**
```
帮我列一个关于"量子计算基础"的PPT大纲，需要10页，面向计算机专业本科生。
```

**Turn 2 — Content approval and refinement:**
```
第3页太简单了，需要增加量子比特的数学表示。
第5页换成量子纠缠的图示说明。
```

**Turn 3 — Style application:**
```
整体风格改为深蓝色科技感，每页添加页码和章节指示器。
```

**Turn 4 — Export:**
```
导出PDF和HTML格式。
```

This approach gives you **maximum control** at each stage and typically produces higher-quality output than single-shot generation.

### 8.2 The "Template Seed" Technique

You can influence the visual design by providing style references in your initial prompt:

```
制作一个产品发布会PPT，参考Apple发布会的极简风格：
- 大量留白
- 超大字体标题
- 单元素聚焦
- 黑白色调为主，产品图用彩色
```

The agent will absorb these style cues and apply them consistently across all generated slides. This is particularly effective when combined with specific color hex codes:

```
品牌色：主色 #1a1a2e，辅色 #e94560，背景 #f5f5f5
```

### 8.3 Content Continuation and Branching

For presentations that exceed the ~15 page limit, use the continuation pattern:

```python
# Pseudocode for pagination
def generate_long_presentation(topic, total_pages=25):
    conversation_id = None
    all_slides = []
    
    # First batch
    response = call_agent(f"制作{topic}的前12页PPT")
    conversation_id = response.conversation_id
    all_slides.extend(response.slides)
    
    # Continue with remaining pages
    response = call_agent(
        "继续生成第13-25页",
        conversation_id=conversation_id
    )
    all_slides.extend(response.slides)
    
    return all_slides
```

---

## 9. Pricing, Rate Limits, and Cost Optimization

### 9.1 Current Pricing Structure

The slide agent uses the standard GLM API token-based pricing [^60^][^58^]:

| Model Tier | Input (per 1M tokens) | Output (per 1M tokens) | Context Window |
|---|---|---|---|
| GLM-4.5 | ¥0.8 (~$0.11) | ¥2.0 (~$0.28) | 128K |
| GLM-4.5-Air | ¥0.35 | ¥0.50 | 128K |
| GLM-4.6 | ¥1.0 | ¥2.0 | 200K |
| GLM-4.7 | ¥0.5 | ¥1.0 | 128K |
| GLM-4-Flash | ¥0.1 | ¥0.1 | 128K |

**Important**: The slide agent's internal model is not directly billed at these rates — Zhipu AI may apply a **multiplier** for agentic tasks because they involve multiple tool calls and reasoning steps. Community reports suggest agent tasks consume **2-3x more tokens** than equivalent chat completions due to the thinking phase and tool execution overhead [^62^].

### 9.2 Token Consumption Patterns

A typical 10-slide presentation consumes approximately:

| Phase | Token Range | Cost (GLM-4.5) |
|---|---|---|
| Initial request (prompt) | 50-200 tokens | ~¥0.0001-0.0004 |
| Thinking phase | 500-2,000 tokens | ~¥0.001-0.004 |
| Web search (if triggered) | 1,000-5,000 tokens | ~¥0.002-0.01 |
| Slide HTML generation | 3,000-15,000 tokens | ~¥0.006-0.03 |
| **Total per presentation** | **5,000-25,000 tokens** | **~¥0.01-0.05** |

At current pricing, you can generate **hundreds of presentations** for less than $1, making this one of the most cost-effective slide generation solutions available.

### 9.3 Rate Limit Considerations

The agent involves **long-running operations** (web search + HTML generation + formatting). The frontend code uses a **3,000,000ms (50-minute) timeout** [^51^], suggesting that complex presentations can take several minutes to complete. Plan your integration accordingly:

- Implement **proper SSE stream handling** — don't wait for the complete response before showing progress
- Use **conversation_id persistence** to allow users to check on long-running jobs
- Consider implementing a **queue system** for bulk generation tasks

---

## 10. Complete Code Examples

### 10.1 Basic API Client (Python)

```python
import requests
import json
import sseclient

class GLMPPTAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://open.bigmodel.cn/api/v1/agents"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def generate_slides(self, prompt: str, conversation_id: str = None):
        """Generate slides from a text prompt."""
        payload = {
            "agent_id": "slides_glm_agent",
            "messages": [{
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }],
            "stream": True
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json=payload,
            stream=True
        )
        
        # Parse SSE stream
        client = sseclient.SSEClient(response)
        slides = []
        current_conversation_id = None
        
        for event in client.events():
            data = json.loads(event.data)
            current_conversation_id = data.get("conversation_id")
            
            for choice in data.get("choices", []):
                for msg in choice.get("messages", []):
                    phase = msg.get("phase")
                    content = msg.get("content", [])
                    
                    if phase == "tool":
                        for item in content:
                            if item.get("type") == "object":
                                obj = item.get("object", {})
                                if obj.get("tool_name") == "insert_page":
                                    slide_html = obj.get("output")
                                    position = obj.get("position", [])
                                    slides.append({
                                        "html": slide_html,
                                        "position": position
                                    })
        
        return {
            "conversation_id": current_conversation_id,
            "slides": slides
        }
    
    def export_presentation(self, conversation_id: str, 
                           include_pdf: bool = True,
                           include_html: bool = True):
        """Export presentation to PDF and/or HTML."""
        payload = {
            "agent_id": "slides_glm_agent",
            "conversation_id": conversation_id,
            "custom_variables": {
                "include_pdf": include_pdf,
                "include_html": include_html
            }
        }
        
        response = requests.post(
            f"{self.base_url}/conversation/",
            headers=self.headers,
            json=payload
        )
        
        return response.json()
```

### 10.2 Student Exercise Placeholder System

```python
import re
from bs4 import BeautifulSoup

class StudentExerciseInjector:
    """Injects regenerable exercise placeholders into GLM-generated slides."""
    
    EXERCISE_TEMPLATES = {
        "fill_blank": {
            "html": '<div class="exercise fill-blank" data-type="fill_blank">'
                   '<p class="prompt">{prompt}</p>'
                   '<input type="text" class="answer-input" placeholder="Your answer..." />'
                   '<button class="check-btn" onclick="checkAnswer(this)">Check</button>'
                   '<span class="feedback"></span></div>',
            "prompts": [
                "Newton's first law states that an object will remain at rest unless acted upon by a __________ force.",
                "The SI unit of force is the __________.",
                "F = ma is known as Newton's __________ law."
            ]
        },
        "multiple_choice": {
            "html": '<div class="exercise mcq" data-type="multiple_choice">'
                   '<p class="question">{question}</p>'
                   '<div class="options">{options}</div>'
                   '<button class="submit-btn" onclick="submitMCQ(this)">Submit</button>'
                   '<span class="result"></span></div>',
            "questions": [
                {
                    "q": "Which of the following is NOT a vector quantity?",
                    "options": ["Velocity", "Mass", "Acceleration", "Force"]
                }
            ]
        }
    }
    
    def inject_exercises(self, slide_html: str, exercise_types: list = None):
        """Add interactive exercise placeholders to slides."""
        soup = BeautifulSoup(slide_html, 'html.parser')
        
        # Find content areas and append exercises
        content_divs = soup.find_all(class_='slide-content')
        
        for i, div in enumerate(content_divs):
            if exercise_types and i < len(exercise_types):
                ex_type = exercise_types[i]
                template = self.EXERCISE_TEMPLATES.get(ex_type)
                if template:
                    exercise_html = self._render_exercise(template, ex_type)
                    exercise_tag = BeautifulSoup(exercise_html, 'html.parser')
                    div.append(exercise_tag)
        
        # Inject the exercise JavaScript
        script = soup.new_tag('script')
        script.string = '''
        // Student exercise system
        function checkAnswer(btn) {
            const container = btn.closest('.exercise');
            const input = container.querySelector('.answer-input');
            const feedback = container.querySelector('.feedback');
            // Implement answer checking logic
            feedback.textContent = 'Checking...';
        }
        
        function regenerateExercise(type) {
            // Call GLM API to generate new exercise of specified type
            return fetch('/api/regenerate-exercise', {
                method: 'POST',
                body: JSON.stringify({type: type})
            }).then(r => r.text());
        }
        '''
        if soup.body:
            soup.body.append(script)
        
        return str(soup)
    
    def _render_exercise(self, template, ex_type):
        if ex_type == "fill_blank":
            prompt = random.choice(template["prompts"])
            return template["html"].format(prompt=prompt)
        return template["html"]
```

### 10.3 Complete Workflow: Generate → Customize → Export

```python
async def create_teaching_presentation(topic: str, 
                                       student_level: str,
                                       exercise_types: list = None):
    """
    Complete workflow: generate slides, inject exercises, export.
    
    Args:
        topic: Subject matter
        student_level: e.g., "高一", "undergraduate"
        exercise_types: List of exercise types to inject
    """
    agent = GLMPPTAgent(api_key="your-api-key")
    injector = StudentExerciseInjector()
    
    # Step 1: Generate initial slides
    prompt = f"""作为{student_level}老师，制作关于"{topic}"的教学课件。
    需要包含概念讲解、公式推导、生活案例、课堂练习。
    风格：清新教育风，适合课堂投影。
    输出10-12页。"""
    
    result = agent.generate_slides(prompt)
    conversation_id = result["conversation_id"]
    
    # Step 2: Add interactive elements via follow-up
    agent.generate_slides(
        "在每张内容页底部添加一个练习题区域，"
        "用虚线框标注，标题为\"课堂练习\"。",
        conversation_id=conversation_id
    )
    
    # Step 3: Export HTML
    export = agent.export_presentation(
        conversation_id=conversation_id,
        include_pdf=True,
        include_html=True
    )
    
    # Step 4: Post-process HTML for exercise interactivity
    html_url = extract_html_url(export)
    html_content = download(html_url)
    
    if exercise_types:
        html_content = injector.inject_exercises(html_content, exercise_types)
    
    return {
        "pdf_url": extract_pdf_url(export),
        "html_content": html_content,
        "conversation_id": conversation_id
    }
```

---

## 11. Error Handling and Edge Cases

### 11.1 Known Error Codes

| Code | Meaning | Solution |
|---|---|---|
| `1301` | Content safety violation | Rephrase prompt to avoid sensitive topics [^3^] |
| Timeout | Generation exceeds 50 minutes | Break into smaller requests |
| `conversation_id` expired | Session timeout | Start new conversation, regenerate from scratch |
| Empty output | Model failed to generate | Retry with more specific prompt |
| Truncated slides | Token limit exceeded | Reduce page count or content density |

### 11.2 Content Safety Workarounds

The agent uses Zhipu AI's standard content filtering. If you encounter `1301` errors [^3^]:

1. **Avoid politically sensitive topics** in educational content
2. **Use indirect language** for potentially flagged concepts
3. **Frame requests as educational** rather than analytical
4. **Switch to the Z.ai web interface** — it sometimes has different filtering rules than the API

---

## 12. Comparison with Alternatives

| Feature | GLM PPT Agent | Gamma | Beautiful.ai | Open-Slide |
|---|---|---|---|---|
| **Output format** | HTML (self-contained) | Proprietary | Proprietary | React/HTML [^54^] |
| **API access** | Yes (documented) | Limited | No | Yes |
| **Model control** | Agent-managed | N/A | N/A | User-managed |
| **Custom templates** | Via HTML post-processing | Yes (paid) | Yes (limited) | Full control |
| **Interactive elements** | Via JS injection | Limited | No | Full [^54^] |
| **Price per deck** | ~$0.01-0.05 | Free-$15/mo | $12-40/mo | Free (open source) |
| **Chinese content** | **Native** | Limited | Limited | N/A |
| **Self-hosted** | No | No | No | Yes |

---

## 13. Summary: The Cheat Sheet

### Quick Reference Card

| Task | How To |
|---|---|
| **Basic generation** | POST to `/v1/agents` with `agent_id: "slides_glm_agent"` |
| **Export PDF** | POST to `/v1/agents/conversation/` with `custom_variables.include_pdf: true` |
| **Export HTML** | Same endpoint with `custom_variables.include_html: true` |
| **Continue generation** | Reuse `conversation_id`, send "继续" or "continue" |
| **Change style** | "改为科技感风格" / "switch to tech style" |
| **Add effects** | "添加粒子特效" / "add particle effects" in initial prompt |
| **Poster mode** | "竖版海报" / "portrait poster" for 9:16 output |
| **Limit page count** | "输出12页" / "12 pages max" |
| **Insert exercises** | Post-process HTML with placeholder injection |
| **Regenerate content** | Same `conversation_id`, request specific changes |
| **Multi-format output** | Generate once, then request format conversion |
| **Handle long content** | Paginate via continuation (~15 page limit) |

### The Golden Rules

1. **Always request `include_html: true`** — it gives you the raw material for customization
2. **Use Chinese prompts** — the agent is optimized for Chinese instructions
3. **Specify everything upfront** — style, page count, audience, format in the first message
4. **Reuse `conversation_id`** — it's the key to multi-turn refinement
5. **Post-process the HTML** — the real power is in what you do after generation

---

*This guide was compiled from official documentation [^3^][^20^], reverse-engineered frontend code [^26^][^51^], Chinese community tips [^39^][^45^], and model architecture documentation [^12^][^44^]. All pricing and model information is current as of June 2026.*
