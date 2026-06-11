import sys

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

# Add the file type validation back
upload_func = """
@app.post("/upload")
async def upload_file(file: UploadFile = File(...), type: str = Form("file")):
    \"\"\"Enhanced upload endpoint to handle prime parsing and style extraction.\"\"\"

    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg", "csv", "txt", "md"}
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
"""

import re
content = re.sub(r"@app\.post\(\"/upload\"\)\s+async def upload_file.*?\"\"\"", upload_func.strip(), content, flags=re.DOTALL)

with open(filename, "w") as f:
    f.write(content)
