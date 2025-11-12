#!/usr/bin/env python3
# ============================================================
# dynamic_rules.py – Enhanced AI Rule Generator (v3)
# ============================================================

import json, re, os
from llm_client import query_llm

SAFE_AUTOFIX_KEYWORDS = [
    "Newtonsoft.Json", "Swashbuckle", "SqlConnection",
    "ConfigurationManager", "HttpContext", "System.Data.SqlClient"
]

def generate_dynamic_rules(project_json: str, diag: str, code_patterns: list):
    """
    Uses AI to infer dynamic migration rules from diagnostics and code patterns.
    Returns a list of structured rule dicts.
    """

    # Expand context length for better understanding (up to 8k chars)
    diag_excerpt = diag[:8000] if diag else ""
    code_excerpt = json.dumps(code_patterns[:30], indent=2)

    prompt = f"""
You are an expert .NET migration analyst.
From the following build diagnostics and code patterns, infer practical migration rules.
Each rule must have:
- id (AUTO-R###)
- pattern (string to match)
- issue (plain text)
- recommendation (clear fix)
- autofix (true/false)

Focus on realistic upgrade issues (e.g., ConfigurationManager removed, HttpContext.Current, Newtonsoft.Json, SqlClient, etc.).

PROJECT:
{project_json}

DIAGNOSTICS (trimmed):
{diag_excerpt}

CODE PATTERNS:
{code_excerpt}
"""

    try:
        response = query_llm(prompt, max_tokens=1200, temperature=0.25)
        rules = json.loads(response) if response.strip().startswith("[") else []
    except Exception:
        rules = []

    # 🧩 Post-process: normalize & tag safe autofix rules
    processed = []
    for i, rule in enumerate(rules or []):
        rid = rule.get("id") or f"AUTO-R{i:03}"
        pattern = rule.get("pattern", "")
        issue = rule.get("issue", "Unspecified issue")
        recommendation = rule.get("recommendation", "Review manually.")
        autofix = rule.get("autofix", False)

        # Mark safe autofix if pattern matches known library
        if any(k.lower() in pattern.lower() for k in SAFE_AUTOFIX_KEYWORDS):
            autofix = True

        processed.append({
            "id": rid,
            "pattern": pattern,
            "issue": issue,
            "recommendation": recommendation,
            "autofix": autofix
        })

    print(f"🧠 Generated {len(processed)} dynamic rules")
    return processed
