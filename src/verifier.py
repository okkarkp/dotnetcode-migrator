#!/usr/bin/env python3
# Layer 4 Verifier v3
import re, pathlib, time
from utils import run_cmd, file_text, write_text, backup_file, restore_backup, has_build_success
from llm_client import query_llm

def _build(proj_dir: pathlib.Path):
    log = run_cmd(["dotnet","build","--nologo","-v","m","--no-incremental"], cwd=proj_dir)
    return has_build_success(log), log

def _ensure_pkg(csproj: pathlib.Path, pkg: str):
    text = file_text(csproj)
    if pkg in text: return False
    line = f'  <PackageReference Include="{pkg}" Version="9.0.0" />\n'
    text = text.replace("</Project>", f"<ItemGroup>\n{line}</ItemGroup>\n</Project>")
    write_text(csproj, text)
    print(f"📦 Ensured {pkg}")
    return True

def _deterministic_pass(proj_dir: pathlib.Path, log: str) -> bool:
    csproj = next(proj_dir.rglob("*.csproj"))
    fixed = False
    if "SqlConnection" in log:
        fixed |= _ensure_pkg(csproj, "Microsoft.Data.SqlClient")
    if "ConfigurationManager" in log:
        for pkg in ["Microsoft.Extensions.Configuration","Microsoft.Extensions.Configuration.Json","Microsoft.Extensions.Configuration.Binder"]:
            fixed |= _ensure_pkg(csproj, pkg)
    if "HttpContext" in log:
        for cs in proj_dir.rglob("*.cs"):
            t = file_text(cs)
            if "HttpContext.Current" in t:
                backup_file(cs)
                write_text(cs, t.replace("HttpContext.Current", "/* Inject IHttpContextAccessor */"))
                fixed = True
    return fixed

def verify_and_retry(tmp_proj_dir: str, max_retries: int = 3):
    proj_dir = pathlib.Path(tmp_proj_dir)
    for attempt in range(1, max_retries+1):
        ok, log = _build(proj_dir)
        if ok:
            print(f"✅ Build succeeded after {attempt-1} retries.")
            return True, log
        print(f"🔍 Verifier pass {attempt}: scanning deterministic fixes…")
        if _deterministic_pass(proj_dir, log):
            ok2, log2 = _build(proj_dir)
            if ok2:
                print("✅ Build recovered deterministically.")
                return True, log2
            log = log2
        err_line = next((l for l in log.splitlines() if "error " in l), "")
        if err_line:
            reply = query_llm(f"Suggest a minimal C# fix for:\n{err_line}", max_tokens=200)
            print(f"🤖 AI micro-fix suggestion: {reply[:120]}")
        time.sleep(1)
    return _build(proj_dir)
