#!/usr/bin/env python3
# learning_db.py – v3 (with rule decay + weighted scoring)

import sqlite3, json, pathlib, time

DB_PATH = pathlib.Path("/opt/oss-migrate/upgrade-poc/upgrade_memory.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ai_rules_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id TEXT,
        pattern TEXT,
        recommendation TEXT,
        project TEXT,
        error_codes TEXT,
        build_success INTEGER,
        confidence REAL DEFAULT 1.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit(); conn.close()

def log_rule_result(rule_id, pattern, recommendation, project, errors, success, confidence=1.0):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO ai_rules_log(rule_id,pattern,recommendation,project,error_codes,build_success,confidence) "
        "VALUES (?,?,?,?,?,?,?)",
        (rule_id, pattern, recommendation, project, json.dumps(errors), int(success), confidence)
    )
    conn.commit(); conn.close()

def query_successful_scored(pattern_like: str, limit=5, decay_weight=0.9):
    """
    Returns learned rules ordered by:
    score = (avg_success_rate * avg_confidence * decay_factor)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)

    cur = conn.execute("""
        SELECT pattern, recommendation,
               AVG(build_success), AVG(confidence),
               (strftime('%s','now') - strftime('%s', created_at)) as age_seconds
        FROM ai_rules_log
        WHERE pattern LIKE ?
        GROUP BY pattern, recommendation
        ORDER BY age_seconds ASC
    """, (f"%{pattern_like}%", ))

    rows = cur.fetchall()
    conn.close()

    processed = []
    for pattern, rec, avg_success, avg_conf, age_sec in rows:
        decay_factor = decay_weight ** (age_sec / (60*60*24))   # per day decay
        score = avg_success * avg_conf * decay_factor
        processed.append((pattern, rec, float(score)))

    processed = sorted(processed, key=lambda x: x[2], reverse=True)
    return processed[:limit]
