#!/usr/bin/env python3
# Layer 2/3 AI-Python Fixer v5
import pathlib, re
from utils import run_cmd, file_text, write_text, backup_file, restore_backup, has_build_success

def validate_build(proj_dir: pathlib.Path):
    log = run_cmd(["dotnet","build","--nologo","-v","m","--no-incremental"], cwd=proj_dir)
    return has_build_success(log), log

def _ensure_package(csproj: pathlib.Path, pkg: str, version: str = None):
    text = file_text(csproj)
    if pkg in text:
        return False
    line = f'  <PackageReference Include="{pkg}"' + (f' Version="{version}"' if version else "") + ' />\n'
    new_text = re.sub(r"(</ItemGroup>)", line + r"\1", text, count=1)
    if new_text == text:
        new_text = text.replace("</Project>", f"<ItemGroup>\n{line}</ItemGroup>\n</Project>")
    write_text(csproj, new_text)
    print(f"📦 Ensured {pkg}{' '+version if version else ''}")
    return True

def _incremental_try_build_after_file_edit(proj_dir: pathlib.Path, edited_file: pathlib.Path) -> bool:
    ok, log = validate_build(proj_dir)
    if not ok:
        restore_backup(edited_file)
        print(f"↩️ Reverted {edited_file.name} due to build break")
        return False
    return True

def _apply_text_sub(file_path: pathlib.Path, pattern: str, recommendation: str) -> bool:
    text = file_text(file_path)
    if pattern not in text:
        return False
    backup_file(file_path)
    fixed = text.replace(pattern, recommendation)
    write_text(file_path, fixed)
    print(f"🧠 AI-sub in {file_path.name}: '{pattern}' → '{recommendation[:60]}...'")
    return True

def run_autofix_pipeline(proj_dir: pathlib.Path, rules: list):
    applied = []
    csproj = next(proj_dir.rglob("*.csproj"))
    for r in rules:
        patt = (r.get("pattern") or "").lower()
        if "sqlconnection" in patt:
            _ensure_package(csproj, "Microsoft.Data.SqlClient")
        if "configurationmanager" in patt:
            _ensure_package(csproj, "Microsoft.Extensions.Configuration")
            _ensure_package(csproj, "Microsoft.Extensions.Configuration.Json")
            _ensure_package(csproj, "Microsoft.Extensions.Configuration.Binder")
    for r in rules:
        if not r.get("autofix"): 
            continue
        rid = r.get("id","AUTO-RXXX")
        patt = r.get("pattern","")
        rec  = r.get("recommendation","")
        for cs in proj_dir.rglob("*.cs"):
            if _apply_text_sub(cs, patt, rec):
                if _incremental_try_build_after_file_edit(proj_dir, cs):
                    applied.append(rid)
    return applied
