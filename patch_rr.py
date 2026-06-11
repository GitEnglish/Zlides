import sys

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

# Update the RR format string to ensure the annotation/exercise script gets injected correctly
rr_format_patch = """
FORMATS = {
    "slides": "Create a multi-slide HTML presentation. Use <section> tags for each slide with page-break-after CSS. Include a title slide, content slides, and a closing slide as appropriate.",
    "poster": "Create a single-page HTML poster. Everything visible on one screen/page. Eye-catching, visual, information-dense.",
    "worksheet": "Create an HTML worksheet with exercises, fill-in-the-blank, matching, or short answer sections. Include numbered exercises with clear instructions. Use HTML form elements (input, checkbox) for interactive fields but NO <script> tags — any interactivity must be CSS-only.",
    "report": "Create an HTML document/report. Structured with headings, paragraphs, lists, and tables as needed. Professional document layout suitable for printing.",
    "rr": "Create an HTML learning resource. Where content can be regenerated (exercises, example sentences, vocabulary lists, practice questions), place <button id='regenerate' data-prompt='SPECIFIC regeneration instruction here'> with a clear label. Do NOT put regenerate buttons on static content like instructions or explanations — only where it makes pedagogical sense to generate new variants. Add inline styles for .regenerate-btn.",
}
"""

import re
content = re.sub(r"FORMATS = \{.*?\n\}", rr_format_patch.strip(), content, flags=re.DOTALL)

with open(filename, "w") as f:
    f.write(content)
