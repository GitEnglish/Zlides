# GLM PPT Slide Agent — Code Execution, Skills & Function Calling: The Real Story

## TL;DR

The GLM PPT Slide Agent (`slides_glm_agent`) **does NOT natively execute Python code or run custom skills**. Its tool suite is limited to slide-specific operations (`search`, `insert_page`, `remove_slides`, `access_page`, `modify_page`). However, the underlying GLM-4/4.5/4.7 models DO have a **Code Interpreter** capability through the "All Tools" mode. The practical play is a **two-step pipeline**: use the chat completions API (with Code Interpreter enabled) to generate data/charts, then feed results into the slide agent — or use the Z.ai web interface with "All Tools" toggled on for a unified experience.

---

## 1. What the Slide Agent Can and Cannot Do

### The Slide Agent's Actual Tool Suite

Based on reverse-engineering the frontend code and official documentation [^3^][^29^][^51^], the slide agent's native capabilities are strictly limited to slide manipulation:

| Tool | Status | What It Does |
|---|---|---|
| `search` | Documented [^3^] | Web search for content |
| `insert_page` | Documented [^3^] | Create slide HTML |
| `remove_slides` | Documented [^3^] | Delete slides |
| `access_page` | Undocumented [^29^] | Navigate between slides |
| `modify_page` | Undocumented [^29^] | Edit existing slides |

**Notably absent**: There is **no `code_interpreter` tool**, no `python_exec` tool, and no mechanism for running arbitrary code within the slide agent context. The agent is a **presentation generator**, not a compute environment.

### Why This Matters for Your Use Case

If you're building interactive slides for students and want dynamic elements like:
- Auto-generated charts from data
- Mathematical equation solving
- Real-time calculations
- Data visualizations

You need to handle these **outside** the slide agent and inject the results as HTML.

---

## 2. GLM's Code Interpreter: Where It Lives (and Where It Doesn't)

### GLM-4 "All Tools" Mode — The Full Capability

When GLM-4 launched in January 2024, Zhipu AI announced the **"All Tools" capability** (All Tools能力) [^106^][^109^][^110^]. This mode enables the model to autonomously:

- Call **Code Interpreter** (代码解释器) for Python execution [^106^]
- Perform **web search** via WebGLM [^109^]
- Generate **images** via CogView3 [^110^]
- Handle **file processing** (Excel, PDF, PPT) [^107^]
- Execute **data analysis and chart plotting** [^106^]

The demo at the launch event showed GLM-4 querying 10 years of global GDP data, generating Python code to visualize it, and overlaying polynomial regression predictions — all triggered by a single natural language prompt [^106^][^110^].

### Where Code Interpreter Is Available

| Platform | Code Interpreter? | How to Access |
|---|---|---|
| **Z.ai Chat UI** (chat.z.ai) | **Yes** — toggle "All Tools" mode | Web interface, select All Tools before prompting [^106^] |
| **Chat Completions API** | **Yes** — via `tools` parameter | Pass `tools` with function definitions [^116^] |
| **`slides_glm_agent` API** | **No** | Not exposed through this endpoint [^3^] |
| **Z.ai SDK** (`zai-sdk`) | **Partial** — only through chat API, not agent | `client.chat.completions.create(tools=[...])` [^116^] |

---

## 3. The Practical Architecture: Two-Stage Pipeline

For slide generation WITH code execution, you need to **orchestrate two separate API calls**:

```
Stage 1: Chat API + Code Interpreter → Generate charts/data
                    ↓
Stage 2: Slide Agent API → Inject results into slides
```

### Stage 1: Generate Charts/Data with Code Interpreter

```python
import json
import requests
import base64

API_KEY = "your-api-key"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def generate_chart_with_code_interpreter(data_description: str) -> str:
    """
    Use GLM's chat completions API with function calling to generate
    a chart. The model will write and execute Python code.

    Note: GLM-4 'All Tools' mode handles this automatically in the
    chat UI, but via API you need to implement the tool execution
    yourself.
    """

    # Prompt asking the model to generate a chart
    response = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        headers=HEADERS,
        json={
            "model": "glm-4.7",
            "messages": [
                {
                    "role": "user",
                    "content": f"""Write Python code using matplotlib to generate a chart for:
{data_description}

Requirements:
- Use matplotlib with a clean, professional style
- Save the chart as a base64-encoded PNG
- Return ONLY the base64 string, no explanation
- Use a color scheme suitable for educational slides (blues/greens)
- Ensure the chart is readable at 800x600 resolution"""
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4096
        }
    )

    result = response.json()
    code_output = result["choices"][0]["message"]["content"]

    # Extract Python code from the response (it's typically wrapped in ```python blocks)
    import re
    code_match = re.search(r'```python\n(.*?)\n```', code_output, re.DOTALL)
    if code_match:
        python_code = code_match.group(1)
    else:
        python_code = code_output

    # Execute the generated code in a sandboxed environment
    # (Use docker, e2b.dev, or a restricted subprocess)
    chart_base64 = execute_sandboxed_code(python_code)

    return chart_base64

def execute_sandboxed_code(code: str) -> str:
    """Execute generated Python code in a restricted environment."""
    import io
    import sys
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt

    # Create restricted globals
    safe_globals = {
        '__builtins__': {
            'range': range, 'len': len, 'str': str, 'int': int,
            'float': float, 'list': list, 'dict': dict, 'zip': zip,
            'enumerate': enumerate, 'sum': sum, 'min': min, 'max': max,
        },
        'plt': plt,
        'matplotlib': matplotlib,
        'base64': __import__('base64'),
        'io': io,
        'json': json,
        'numpy': __import__('numpy'),
    }

    # Capture the base64 output
    output_buffer = io.StringIO()
    sys.stdout = output_buffer

    try:
        exec(code, safe_globals)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        sys.stdout = sys.__stdout__
        plt.close('all')

    # The code should have saved a base64 string to stdout
    return output_buffer.getvalue().strip()
```

### Stage 2: Inject Charts into Slides

```python
def create_slide_with_chart(topic: str, chart_base64: str, explanation: str) -> dict:
    """
    Send chart data to the slide agent to create a slide containing it.
    """

    prompt = f"""创建一个包含数据图表的教学幻灯片。

主题：{topic}

图表数据（base64编码PNG图片）：
data:image/png;base64,{chart_base64[:100]}...

要求：
- 在图表上方添加标题和简要说明
- 图表下方添加"分析要点"区域，包含3个要点
- 右下角添加"数据来源"标注
- 整体风格：教育风，蓝色系
"""

    response = requests.post(
        "https://open.bigmodel.cn/api/v1/agents",
        headers=HEADERS,
        json={
            "agent_id": "slides_glm_agent",
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "stream": True
        },
        stream=True
    )

    # Parse SSE stream... (same as in the main guide)
    return parse_slide_response(response)
```

---

## 4. Alternative: E2B.dev for Sandboxed Code Execution

For production use, a cleaner approach is to use a dedicated sandbox service like **E2B.dev** [^102^]:

```python
from e2b_code_interpreter import CodeInterpreter
import json

def generate_chart_e2b(data_query: str, api_key: str) -> dict:
    """
    Use E2B sandbox for secure Python code execution.
    The LLM generates code, E2B executes it safely.
    """

    code_interpreter = CodeInterpreter(api_key=api_key)

    # First, ask GLM to generate the Python code
    code_response = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        headers=HEADERS,
        json={
            "model": "glm-4.7",
            "messages": [
                {
                    "role": "user",
                    "content": f"Write Python code to generate a matplotlib chart for: {data_query}. "
                               f"Save it as '/home/user/chart.png'. Include proper labels, title, and grid."
                }
            ]
        }
    ).json()

    generated_code = code_response["choices"][0]["message"]["content"]

    # Execute in E2B sandbox
    execution = code_interpreter.notebook.exec_cell(generated_code)

    # Read the generated chart file from sandbox
    chart_file = code_interpreter.files.read("/home/user/chart.png")
    chart_base64 = base64.b64encode(chart_file).decode('utf-8')

    code_interpreter.close()

    return {
        "chart_base64": chart_base64,
        "stdout": execution.logs.stdout,
        "stderr": execution.logs.stderr
    }
```

---

## 5. Function Calling with GLM: What Works and What Doesn't

### GLM Supports Function Calling (But Not on the Slide Agent Endpoint)

The GLM-4/4.5/4.7 models support **OpenAI-compatible function calling** [^116^][^114^]:

```python
# This works on the chat completions endpoint
response = client.chat.completions.create(
    model="glm-5",
    messages=[{"role": "user", "content": "What's the weather in Beijing?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    }],
    tool_choice="auto"
)
```

But the slide agent endpoint **ignores `tools` parameter entirely**. It's a pre-configured agent with a fixed tool set [^3^].

### The "Skill" Question

If by "skill" you mean **custom function tools** (like OpenAI's function calling or LangChain tools) [^103^][^104^]:

| Platform | Custom Tools? | How |
|---|---|---|
| **Chat Completions API** | **Yes** | Pass `tools` array with JSON schema [^116^] |
| **`slides_glm_agent`** | **No** | Fixed tool set, no custom tool injection |
| **Z.ai Agent Platform** | **Yes** (partial) | Build custom agents with tool definitions [^110^] |

If by "skill" you mean **reusable prompt templates or workflow patterns**:

| Feature | Available? | How |
|---|---|---|
| **System prompts** | **No** on slide agent | Not exposed through agent API |
| **Template saving** | **No** | Must implement externally |
| **Conversation branching** | **Yes** via `conversation_id` | Fork by reusing ID at different states |
| **Prompt libraries** | **Manual only** | Store and reuse prompt text client-side |

---

## 6. The Z.ai Web Interface: The "All Tools" Experience

The smoothest way to get charts + slides together is through the **Z.ai web chat interface** (chat.z.ai) with **"All Tools" mode enabled** [^106^]:

### What Happens in All Tools Mode

1. You type: "Create a presentation about climate change with temperature trend charts"
2. GLM automatically:
   - Searches for climate data
   - Calls Code Interpreter to generate matplotlib charts
   - Creates the slide HTML with embedded chart images
   - Formats everything into a presentation

3. You get a complete presentation with data-driven visualizations

### Limitation

The web UI experience **cannot be replicated via the slide agent API**. The agent API endpoint is a stripped-down version that only handles slide generation, not the full tool orchestration. The web UI uses a different internal orchestration layer that coordinates multiple services.

---

## 7. Complete Architecture for Your Student Slide System

Given everything above, here's the recommended architecture for your use case:

```
┌─────────────────────────────────────────────────────────────────┐
│                      YOUR APPLICATION                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Data/Chart   │  │ Slide Agent  │  │ Student Exercise     │  │
│  │ Generator    │→ │ (slides_glm_ │→ │ Injector (your code) │  │
│  │ (your Python │  │  agent)       │  │                      │  │
│  │  + E2B sandbox│  └──────────────┘  └──────────────────────┘  │
│  └──────────────┘           ↑                                   │
│           ↓                 │                                   │
│  ┌──────────────────────────────────────┐                       │
│  │  Chart Gen → Base64 → Slide Prompt   │                       │
│  │  (matplotlib/Plotly/Seaborn)         │                       │
│  └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Implementation Points

1. **Chart Generation**: Use matplotlib/Plotly in a sandboxed environment (E2B, Docker, or restricted subprocess) to generate charts as base64 PNGs
2. **Slide Creation**: Feed the base64 chart data into the slide agent via the prompt
3. **Exercise Injection**: Post-process the HTML output to add regenerable exercise placeholders
4. **Regeneration**: When a student clicks "regenerate exercise," call the chat completions API (not the slide agent) to generate new problem text, then update the DOM via JavaScript

---

## 8. Summary Matrix

| Question | Answer | Details |
|---|---|---|
| **Can slide agent run Python?** | **No** | No code execution in `slides_glm_agent` [^3^] |
| **Can GLM models run Python?** | **Yes** | Via Code Interpreter in "All Tools" mode [^106^] |
| **Can slide agent call custom functions?** | **No** | Fixed tool set only |
| **Can chat API call custom functions?** | **Yes** | Full function calling support [^116^] |
| **Can web UI do charts + slides?** | **Yes** | All Tools mode orchestrates everything [^106^] |
| **Can I build a skill system?** | **Partially** | External orchestration required; agent has no native skill framework |
| **Best way to add charts to slides?** | **Two-stage**: Generate charts externally → inject into slide prompts |
| **Safest code execution?** | **E2B.dev** or Docker sandbox [^102^] |

---

## 9. The Bottom Line

The slide agent is a **specialized presentation generator**, not a general-purpose agent. Think of it like a **renderer** — it takes content and produces HTML slides. For anything involving computation, data processing, or dynamic content generation, you need to:

1. **Do the work outside** (Python sandbox, data pipeline, chart generator)
2. **Package results** (base64 images, computed values, generated text)
3. **Feed into the agent** as enriched prompts
4. **Post-process output** (inject interactivity, annotations, exercise placeholders)

This is actually **superior architecture** for your use case because it gives you full control over the computation layer while leveraging the agent's strength (beautiful slide generation). You're not fighting the agent's limitations — you're complementing them.
