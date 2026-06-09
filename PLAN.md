# Zlides Upgrade Plan: Formats, Style Bank & GitEnglishHub Integration

## Architecture: Formats ≠ Styles

These are **orthogonal** choices:

**Format** (shape/structure of output):
- `slides` — multi-slide presentation
- `poster` — single-page poster
- `worksheet` — homework/exercises
- `report` — document/report
- `rr` — RegenResource: AI auto-places regenerate buttons where it decides content can be re-generated

**Style** (visual look):
- `auto` — let the agent freestyle (default, no constraints)
- `clean` — white background, professional
- `dark` — dark mode
- `minimal` — black on white, no decoration
- `gitEnglish` — brand colors + gitEnglish PNG branding
- *any custom styles you save to your bank*

You can mix any format with any style. e.g. "worksheet + gitEnglish" or "rr + auto".

---

## The gitEnglish Style

It's a **visual style**, not a format. When selected:

- Colors: #262424 bg, #383535 cards, #ff6600 accent, #e0ded2 text, #555252 borders
- Fonts: Inter (body), Raleway (headings)
- Neumorphic shadows on cards
- **gitEnglish PNG branding** in the corner/footer of every output
- All inline CSS, no Tailwind CDN, no external deps
- Survives `dangerouslySetInnerHTML` + DOMPurify

The PNG branding is always included regardless of format (slides, worksheet, rr — all get the little gitEnglish mark).

---

## The RR Format (RegenResource)

When format = `rr`:

1. The system prompt tells Z.AI: "Analyze this content request. Where you determine content can be auto-regenerated (exercises, examples, sentences, vocabulary), place `<button id="regenerate" data-prompt="...">` with a specific regeneration prompt. Where content is static (instructions, explanations), do NOT place a button."

2. The AI decides the placement — not every section gets one. Only where regeneration makes pedagogical sense.

3. The button contract matches what `TrueDirectHtmlRenderer` already listens for in GitEnglishHub: `id="regenerate"` + `data-prompt` attribute.

4. When rendered in GitEnglishHub, the server injects the backend helper script that handles clicks → `/api/resources/regenerate`.

---

## Style Bank

A personal library of style guides you can save, preview, and reuse.

### Storage
```
zlides/
  style_bank/
    gitenglish.json
    clean.json
    dark.json
    minimal.json
    my-custom-style.json    ← any name you want
```

### Style Pack Schema
```json
{
  "id": "gitenglish",
  "name": "gitEnglish Hub",
  "created_at": "2026-03-30",
  "brand_png": "gitenglish-alt.png",
  "preview_colors": ["#262424", "#383535", "#ff6600", "#e0ded2"],
  "css": {
    "bg": "#262424",
    "card": "#383535",
    "text": "#e0ded2",
    "text_secondary": "#9e9e9e",
    "accent": "#ff6600",
    "accent_hover": "#ff9966",
    "border": "#555252",
    "success": "#5ab244",
    "danger": "#e8514a"
  },
  "fonts": {
    "body": "'Inter', system-ui, sans-serif",
    "heading": "'Raleway', 'Inter', sans-serif"
  },
  "card_style": "neumorphic",
  "system_prompt_suffix": "... extra instructions for Z.AI when using this style ...",
  "print_css": "... @media print overrides ...",
  "compatible_with_dompurify": true
}
```

### How to Add a Style

1. **Upload an image** (screenshot, design reference, mood board)
2. **OR describe it** in text ("neon cyberpunk with purple accents, dark background, monospace font")
3. Z.AI agent analyzes it and generates a style pack JSON
4. **Preview card** shows: color swatches + a tiny rendered sample slide
5. You confirm → saved to `style_bank/`
6. Or reject → discarded

### Endpoints

```python
# List all styles in bank
GET /styles                    → [{id, name, preview_colors, brand_png}]

# Get full style pack
GET /styles/{id}               → full JSON

# Create style from image or description (agent analyzes)
POST /styles/create
  Body: { "image_file_id": "...", "description": "..." }
  Response: { "preview": {...}, "proposed": {...} }  # shows before confirming

# Confirm and save a previewed style
POST /styles/save
  Body: { "style": {...} }
  Response: { "saved": true, "id": "..." }

# Delete a style
DELETE /styles/{id}

# The "auto" option is implicit — no style pack loaded, agent freestyles
```

### Frontend: Style Picker

Replace the current Theme dropdown with:

```
Format:  [slides ▼]  [poster] [worksheet] [report] [rr]
Style:   [auto ▼]    [clean] [dark] [minimal] [gitEnglish] [+ Add Style]
```

- `[auto]` = no style constraints, agent decides everything
- `[gitEnglish]` = your branded style (has a tiny orange dot indicator)
- `[+ Add Style]` = opens the style creation panel (upload image or describe)
- Saved styles show a **color swatch row** next to their name

When gitEnglish is selected, the preview iframe gets a dark background.

---

## Export System

### PDF Export
`window.print()` with per-style `@media print` CSS. Each style pack includes print CSS that:
- Hides regenerate buttons (`.no-print { display: none }`)
- Sets proper margins (@page A4)
- Ensures contrast works on paper (dark styles get inverted for print)

### HTML Fragment Export (for GitEnglishHub → Sanity)

Strips `<!DOCTYPE>`, `<html>`, `<head>`, `<body>` — just the content + `<style>` block.
This goes into the `content` field (plain `text` type) on `studentResource` in Sanity.

**Target field**: `studentResource.content` (type: text, rows: 25 in schema)
**Rendering**: `TrueDirectHtmlRenderer` via `dangerouslySetInnerHTML`

### What Survives the Trip

The exported fragment must only contain tags from DOMPurify allowlist:
- p, br, strong, b, em, i, u, h1-h6, ul, ol, li, a, img, div, span
- blockquote, code, pre, table, thead, tbody, tr, td, th, hr, sub, sup
- Plus: **style** (for CSS), **button** (for regenerate)

**No `<script>` tags**. Interactivity = CSS-only OR the `id="regenerate"` button which GitEnglishHub server handles.

---

## Implementation Order

### 1. Backend: Format + Style Engine (slide_server.py)
- Add `format` and `style` fields to ChatRequest
- Build format → system prompt mapping
- Build style → CSS injection mapping
- Load style bank from `style_bank/` directory
- GitEnglish style pack (hardcoded first, then extracted to JSON)
- RR format system prompt (AI decides regen button placement)

### 2. Backend: Style Bank CRUD
- `GET /styles` — list
- `GET /styles/{id}` — get one
- `POST /styles/create` — agent analyzes image/description, returns preview
- `POST /styles/save` — confirm save
- `DELETE /styles/{id}` — remove
- `POST /styles/{id}/preview-slide` — generate a test slide with this style

### 3. Backend: Export Endpoints
- `POST /export/html` — full HTML download
- `POST /export/fragment` — DOMPurify-safe fragment (clipboard-ready)
- Print CSS injection per style

### 4. Frontend: New Controls
- Format selector (radio buttons or segmented control)
- Style picker dropdown (from style bank + auto)
- Style creation panel (upload image / type description → preview → save)
- Export bar (PDF / HTML / Fragment / Copy for Sanity)

### 5. GitEnglish Style Pack
- Extract exact CSS from `globals.css` values
- Create `style_bank/gitenglish.json`
- Include brand PNG reference
- Test fragment in TrueDirectHtmlRenderer

### 6. RR Format Testing
- Test regen button placement with various content types
- Verify button contract works through the full pipeline:
  Zlides → fragment → Sanity content → page.tsx injects helper → student clicks → regenerate API

---

## Files to Create/Modify

| File | What |
|------|------|
| `slide_server.py` | Format/style engine, export endpoints, style bank CRUD |
| `index.html` | Format selector, style picker, style creation panel, export bar |
| New: `style_bank/` | Directory with JSON style packs |
| New: `style_bank/gitenglish.json` | Your branded style pack |
| New: `style_bank/clean.json` | Default clean style |
| New: `style_bank/dark.json` | Dark mode style |
| New: `style_bank/minimal.json` | Minimal style |

## NOT Modifying
- `launch.sh` — works fine
- `mcp_wrapper.py` — standalone tool
- GitEnglishHub code — Zlides generates HTML that fits the existing system
