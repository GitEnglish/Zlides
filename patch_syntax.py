import sys

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

bad_str = '            "markdown": "# Parsed Content from " + filename + "\\n\\nHere is extracted text with layout hierarchy preserved.",'
if "Here is extracted text" in content:
    content = content.replace('"markdown": "# Parsed Content from " + filename + "\n\nHere is extracted text with layout hierarchy preserved.",', bad_str)

with open(filename, "w") as f:
    f.write(content)
