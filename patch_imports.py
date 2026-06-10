import sys

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

if "from fastapi import FastAPI, HTTPException, UploadFile, File, Form" not in content:
    content = content.replace(
        "from fastapi import FastAPI, HTTPException, UploadFile, File",
        "from fastapi import FastAPI, HTTPException, UploadFile, File, Form"
    )

with open(filename, "w") as f:
    f.write(content)
