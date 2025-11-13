#!/usr/bin/env python3
# dynamic_rules.py – v12 (Rule Decay + Project Types + Safety)

import json
from llm_client import query_llm
from utils import extract_error_codes
from learning_db import query_successful_scored
from project_type import detect_project_type

SAFE_AUTOFIX_KEYWORDS = [
    "Newtonsoft.Json", "Swashbuckle",
    "SqlConnection", "ConfigurationManager",
    "HttpContext", "IConfiguration",
    "Microsoft.Data.SqlClient"
]

CONFIDENCE_THRESHOLD = 0.70

def generate_dynamic_rules(project_json: str, diag: str, code_patterns: list, csproj_path=None):
    diag_excerpt = (diag or "")[:12000]
    errors = list(sorted(set(extract_error_codes(diag_excerpt))))

    project_type = detect_project_type(csproj_path)
    print(f"📌 Project Type Detected: {project_type}")

    # ---------------------------------------------------------------------
    # 1. Learned rules (decayed + ranked)
    # ---------------------------------------------------------------------
    learned_rules = []
    for patt in errors + [p.get("pattern","") for p in code_patterns]:
        hits = query_successful_scored(patt)
        for pattern, rec, score in hits:
            learned_rules.append({
                "id": f"MEM-R{int(score*100)}",
                "pattern": pattern,
                "issue": f"Learned fix (score={round(score,2)})",
                "recommendation": rec,
                "confidence": score,
                "autofix": score >= 0.80
            })

    if learned_rules:
        print(f"🧠 Loaded {len(learned_rules)} decayed learned rules")

    # ---------------------------------------------------------------------
    # 2. AI Rule Generation
    # ---------------------------------------------------------------------
    prompt = f"""
You are a .NET migration expert.
PROJECT TYPE: {project_type}

Below are proven fixes with decay scoring:
{json.dumps(learned_rules, indent=2)}

Generate NEW rules with:
- id
- pattern
- issue
- recommendation
- confidence (0–1)
- autofix (true/false)

Project JSON:
{project_json}

Error Codes:
{errors}

Diagnostics:
{diag_excerpt}
"""

    ai_rules = []
    try:
        response = query_llm(prompt, max_tokens=1800, temperature=0.2)
        if response.strip().startswith("["):
            ai_rules = json.loads(response)
    except Exception:
        ai_rules = []

    # ---------------------------------------------------------------------
    # 3. Merge + Safety
    # ---------------------------------------------------------------------
    processed = []

    for lr in learned_rules:
        processed.append(lr)

    for i, r in enumerate(ai_rules):
        rid = r.get("id", f"AUTO-R{i:03}")
        patt = r.get("pattern","")
        issue = r.get("issue","")
        rec = r.get("recommendation","")
        conf = float(r.get("confidence", 0.5))
        auto = conf >= CONFIDENCE_THRESHOLD

        if any(k.lower() in patt.lower() for k in SAFE_AUTOFIX_KEYWORDS):
            auto = True

        # SAFETY: Do not autofix in wrong project types
        if project_type in ["worker-service", "console-or-library"]:
            if "HttpContext" in patt or "Swashbuckle" in patt:
                auto = False

        processed.append({
            "id": rid,
            "pattern": patt,
            "issue": issue,
            "recommendation": rec,
            "confidence": conf,
            "autofix": auto
        })

    print(f"🧠 Final rules: {len(processed)} (AI + memory scored + safe filtered)")
    return processed
