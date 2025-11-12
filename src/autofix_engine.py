#!/usr/bin/env python3
# ============================================================
# autofix_engine.py – Smarter Layer-2/3 AI-Python Fixer (v4)
# ============================================================

import os, re, subprocess, pathlib, shutil, json, tempfile

def run_cmd(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return (p.stdout or "") + (p.stderr or "")

def validate_build(proj_dir):
    log = run_cmd(["dotnet", "build", "--nologo", "-v", "m"], cwd=proj_dir)
    success = "Build succeeded" in log or "0 Error(s)" in log
    return success, log

def apply_ai_fix(file_path, pattern, recommendation):
    text = pathlib.Path(file_path).read_text()
    if pattern in text:
        backup = f"{file_path}.bak"
        shutil.copyfile(file_path, backup)
        # naive string substitution
        fixed = text.replace(pattern, recommendation)
        pathlib.Path(file_path).write_text(fixed)
        print(f"🧠 AI autofix applied in {file_path} for pattern '{pattern}'")
        return True
    return False

def ensure_package(csproj, package_name, version="9.0.0"):
    csproj_path = pathlib.Path(csproj)
    text = csproj_path.read_text()
    if package_name not in text:
        line = f'  <PackageReference Include="{package_name}" Version="{version}" />\n'
        new_text = re.sub(r"(</ItemGroup>)", line + r"\1", text, count=1)
        csproj_path.write_text(new_text)
        print(f"📦 Ensured package {package_name} ({version})")
        return True
    return False

def run_autofix_pipeline(proj_dir, rules):
    """Runs sequential autofixes for rules that allow autofix."""
    applied = []
    for rule in rules:
        if not rule.get("autofix"):  # skip non-autofix rules
            continue
        pattern = rule.get("pattern", "")
        rec = rule.get("recommendation", "")
        rid = rule.get("id", "AUTO-RXXX")

        # Look for candidate source files
        for csfile in pathlib.Path(proj_dir).rglob("*.cs"):
            if apply_ai_fix(csfile, pattern, rec):
                applied.append(rid)

        # Smart package enforcement
        if "SqlConnection" in pattern:
            ensure_package(list(pathlib.Path(proj_dir).rglob("*.csproj"))[0], "Microsoft.Data.SqlClient")
        elif "ConfigurationManager" in pattern:
            ensure_package(list(pathlib.Path(proj_dir).rglob("*.csproj"))[0], "Microsoft.Extensions.Configuration")

    return applied
