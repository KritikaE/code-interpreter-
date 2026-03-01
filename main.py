import os
import sys
import traceback
from io import StringIO
from typing import List
import json

import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class CodeRequest(BaseModel):
    code: str

class CodeResponse(BaseModel):
    error: List[int]
    result: str

# --- Part 1: Execute Code ---
def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code, {})
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}
    finally:
        sys.stdout = old_stdout

# --- Part 2: AI Error Analysis (Claude) ---
def analyze_error_with_ai(code: str, tb: str) -> List[int]:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""Analyze this Python code and its error traceback.
Identify the line number(s) where the error occurred.

CODE:
{code}

TRACEBACK:
{tb}

Reply with ONLY a JSON object in this exact format, nothing else:
{{"error_lines": [3]}}
"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    data = json.loads(raw)
    return data["error_lines"]

# --- Handle OPTIONS preflight ---
@app.options("/code-interpreter")
async def options_handler():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

# --- Endpoint ---
@app.post("/code-interpreter")
def code_interpreter(request: CodeRequest):
    execution = execute_python_code(request.code)

    if execution["success"]:
        response_data = {"error": [], "result": execution["output"]}
    else:
        error_lines = analyze_error_with_ai(request.code, execution["output"])
        response_data = {"error": error_lines, "result": execution["output"]}

    return JSONResponse(
        content=response_data,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Access-Control-Allow-Origin",
        }
    )
