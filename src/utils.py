#!/usr/bin/env python3
import subprocess, pathlib, shutil, json, re, os

def run_cmd(cmd, cwd=None, timeout=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return (p.stdout or "") + (p.stderr or "")

def file_text(path: pathlib.Path) -> str:
    return pathlib.Path(path).read_text(errors="ignore")

def write_text(path: pathlib.Path, text: str):
    pathlib.Path(path).write_text(text)

def backup_file(path: pathlib.Path) -> pathlib.Path:
    backup = pathlib.Path(str(path) + ".bak")
    shutil.copyfile(path, backup)
    return backup

def restore_backup(path: pathlib.Path):
    bak = pathlib.Path(str(path) + ".bak")
    if bak.exists():
        shutil.copyfile(bak, path)

def ensure_dir(p: pathlib.Path):
    p.mkdir(parents=True, exist_ok=True)

def extract_error_codes(log: str):
    return re.findall(r"error\s+([A-Z]+\d{3,5})", log or "")

def has_build_success(log: str) -> bool:
    return ("Build succeeded" in log) or (" 0 Error(s)" in log) or ("build succeeded" in log.lower())

def list_csprojs(root: pathlib.Path):
    return list(root.rglob("*.csproj"))

import requests

def push_live_log(line: str):
    try:
        requests.post("http://127.0.0.1:8899/push-log", json={"message": line})
    except:
        pass
