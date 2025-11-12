#!/usr/bin/env python3
"""
Layer 4 – Post-Fix Verifier
Intercepts compiler errors after the AI/autofix layers and re-attempts deterministic or AI-guided corrections.
"""

import re, subprocess, pathlib, time
from llm_client import query_llm
from autofix_ai import generate_code_fix

# ---------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------

def _run_build(tmp_proj_dir: str):
    """Run dotnet build and capture output."""
    p = subprocess.run(
        ["dotnet", "build", str(tmp_proj_dir), "--nologo", "-v", "m"],
        capture_output=True, text=True
    )
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")

def _parse_errors(build_log: str):
    """Extract error codes and short context lines from a build log."""
    errors = []
    for line in build_log.splitlines():
        m = re.search(r"error\s+(CS\d{4}):\s*(.*)", line)
        if m:
            errors.append((m.group(1), m.group(2).strip()))
    return errors

# ---------------------------------------------------------------------
# Deterministic fixes
# ---------------------------------------------------------------------

def _apply_deterministic_fix(tmp_proj_dir: pathlib.Path, code: str, message: str):
    """Apply quick, non-AI fixes for common compiler errors."""
    csproj = next(tmp_proj_dir.rglob("*.csproj"))
    src = tmp_proj_dir
    fixed = False

    if code == "CS0246":  # missing type/namespace
        if "SqlConnection" in message:
            subprocess.run(["dotnet","add",str(csproj),"package","Microsoft.Data.SqlClient","--version","5.2.0"])
            for f in src.rglob("*.cs"):
                t = f.read_text(errors="ignore")
                if "using Microsoft.Data.SqlClient;" not in t:
                    f.write_text("using Microsoft.Data.SqlClient;\n" + t)
            fixed = True
        elif "IConfiguration" in message:
            subprocess.run(["dotnet","add",str(csproj),"package","Microsoft.Extensions.Configuration","--version","9.0.0"])
            fixed = True

    elif code == "CS0103":  # name does not exist
        if "HttpContext" in message:
            for f in src.rglob("*.cs"):
                t = f.read_text(errors="ignore")
                if "HttpContext" in t:
                    f.write_text(t.replace("HttpContext", "/*HttpContext removed*/object"))
            fixed = True

    elif code == "CS1069":  # type forwarded
        if "SqlConnection" in message:
            subprocess.run(["dotnet","add",str(csproj),"package","Microsoft.Data.SqlClient","--version","5.2.0"])
            fixed = True

    return fixed

# ---------------------------------------------------------------------
# AI-guided fix
# ---------------------------------------------------------------------

def _apply_ai_fix(tmp_proj_dir: pathlib.Path, error_snippet: str):
    """Ask LLM to rewrite only minimal section related to the error."""
    prompt = f"""
You are a .NET compiler assistant.
Given this compiler error, propose the minimal C# fix needed.

ERROR:
{error_snippet}

Respond with a corrected code snippet only.
"""
    ai_reply = query_llm(prompt, max_tokens=400, temperature=0.2)
    # naive extract of first code block
    code_block = re.search(r"```(?:csharp|cs)?(.*?)```", ai_reply, re.S)
    if not code_block:
        return False
    snippet = code_block.group(1).strip()
    # find candidate file
    for f in tmp_proj_dir.rglob("*.cs"):
        if "class" in f.read_text(errors="ignore"):
            generate_code_fix(str(f), "/*AI_FIX*/", snippet)
            return True
    return False

# ---------------------------------------------------------------------
# Main verification routine
# ---------------------------------------------------------------------

def verify_and_retry(tmp_proj_dir: str, max_retries: int = 3):
    """Attempt deterministic + AI-guided fixes until build succeeds or retries exhausted."""
    tmp_proj_dir = pathlib.Path(tmp_proj_dir)
    attempt = 0
    while attempt < max_retries:
        success, log = _run_build(tmp_proj_dir)
        if success:
            print(f"✅ Build succeeded after {attempt} verifier retries.")
            return True, log
        attempt += 1
        errors = _parse_errors(log)
        if not errors:
            print("⚠️ Build failed with no recognizable errors.")
            break

        print(f"🔍 Verifier pass {attempt}: found {len(errors)} errors.")
        fixed_any = False
        for code, msg in errors:
            if _apply_deterministic_fix(tmp_proj_dir, code, msg):
                print(f"🛠️ Deterministic fix applied for {code}: {msg}")
                fixed_any = True
            else:
                print(f"🤖 Escalating {code} to AI.")
                fixed_any |= _apply_ai_fix(tmp_proj_dir, f"{code}: {msg}")

        if not fixed_any:
            print("❌ No additional fixes applied; stopping verifier.")
            return False, log

        print("♻️ Rebuilding after verifier fixes...")
        time.sleep(2)

    return _run_build(tmp_proj_dir)
