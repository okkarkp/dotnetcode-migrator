#!/usr/bin/env python3
# Web Dashboard with Live Logs + Rule Viewer + Reports

import asyncio, json, pathlib, sqlite3
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_PATH = pathlib.Path("/opt/oss-migrate/upgrade-poc/upgrade_memory.db")
REPORT_DIR = pathlib.Path("/opt/oss-migrate/upgrade-poc/reports")

app = FastAPI(title="AI Upgrade Dashboard")
BASE_DIR = pathlib.Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=f"{BASE_DIR}/static"), name="static")
templates = Jinja2Templates(directory=f"{BASE_DIR}/templates")

connected_websockets = set()

# ---------------------------------------------------------------
# WebSocket: Live log streaming
# ---------------------------------------------------------------
@app.websocket("/ws/logs")
async def log_socket(ws: WebSocket):
    await ws.accept()
    connected_websockets.add(ws)
    try:
        while True:
            await asyncio.sleep(1)
    except:
        pass
    finally:
        connected_websockets.remove(ws)

async def broadcast_log(text: str):
    dead = []
    for ws in connected_websockets:
        try:
            await ws.send_text(text)
        except:
            dead.append(ws)
    for ws in dead:
        connected_websockets.remove(ws)


# ---------------------------------------------------------------
# Dashboard Home
# ---------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------
# Learned Rules Viewer
# ---------------------------------------------------------------
@app.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT rule_id, pattern, recommendation, build_success, confidence, created_at
        FROM ai_rules_log ORDER BY created_at DESC LIMIT 200
    """)
    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("rules.html", {
        "request": request,
        "rules": rows
    })


# ---------------------------------------------------------------
# Reports Viewer
# ---------------------------------------------------------------
@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    reports = sorted(REPORT_DIR.glob("*_upgrade_summary.md"))
    return templates.TemplateResponse("reports.html", {
        "request": request,
        "reports": [r.name for r in reports]
    })


@app.get("/reports/{name}", response_class=HTMLResponse)
async def read_report(name: str, request: Request):
    path = REPORT_DIR / name
    if not path.exists():
        return HTMLResponse("Report not found", status_code=404)

    text = path.read_text(errors="ignore")
    escaped = text.replace("<","&lt;").replace(">","&gt;")

    return templates.TemplateResponse("report_view.html", {
        "request": request,
        "name": name,
        "text": escaped
    })


# ---------------------------------------------------------------
# API endpoint for live log injection by main.py
# ---------------------------------------------------------------
@app.post("/push-log")
async def push_log(payload: dict):
    msg = payload.get("message","")
    await broadcast_log(msg)
    return {"ok": True}

