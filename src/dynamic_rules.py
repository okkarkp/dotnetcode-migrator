import json, re
from llm_client import query_llm

JUNK_TOKENS = {"PackageName", "ClassName", "MethodName", "TypeName"}

def _looks_valid_pattern(p: str, code_patterns: list) -> bool:
    if not p or any(t in p for t in JUNK_TOKENS):
        return False
    for keep in ("HttpContext", "ConfigurationManager", "SqlConnection",
                 "System.Data.SqlClient", "Microsoft.Data.SqlClient"):
        if keep in p:
            return True
    return any(p.strip("'\"") in cp for cp in code_patterns)

def validate_rule_schema(r):
    required = {"id","pattern","issue","recommendation","autofix"}
    return isinstance(r, dict) and required.issubset(r.keys()) and isinstance(r["pattern"], str)

def generate_dynamic_rules(project_info: str, build_diag: str, code_patterns: list):
    example = """[
      {
        "id": "AUTO-R000",
        "pattern": "HttpContext.Current",
        "issue": "Removed from ASP.NET Core",
        "recommendation": "Use IHttpContextAccessor or remove HttpContext usage in console apps.",
        "autofix": true
      }
    ]"""

    prompt = f"""
Return ONLY a JSON array of rules (no prose).
Each rule: id, pattern, issue, recommendation, autofix.
Prefer actionable API-level patterns found in the codebase.

Example format:
{example}

PROJECT INFO:
{project_info}

BUILD DIAGNOSTICS (trimmed):
{build_diag[:1000]}

CODE PATTERNS (first 12):
{json.dumps(code_patterns[:12], indent=2)}
"""
    text = query_llm(prompt, max_tokens=800, temperature=0.25)

    json_block = re.search(r"\[[\s\S]*\]", text)
    parsed = []
    if json_block:
        try:
            parsed = json.loads(json_block.group())
        except Exception:
            parsed = []

    if not parsed:
        parsed = [{
            "id": "AUTO-R999",
            "pattern": "ConfigurationManager.AppSettings",
            "issue": "Legacy configuration API replaced in modern .NET",
            "recommendation": "Use Microsoft.Extensions.Configuration with injected IConfiguration.",
            "autofix": True
        }]

    cleaned = []
    for r in parsed:
        if not validate_rule_schema(r):
            continue
        if not _looks_valid_pattern(r.get("pattern",""), code_patterns):
            continue
        r["autofix"] = True  # PoC: force on
        cleaned.append(r)
        if len(cleaned) >= 5:
            break

    if not cleaned:
        cleaned = [{
            "id": "AUTO-R999",
            "pattern": "ConfigurationManager.AppSettings",
            "issue": "Legacy configuration API replaced in modern .NET",
            "recommendation": "Use Microsoft.Extensions.Configuration with injected IConfiguration.",
            "autofix": True
        }]

    return cleaned
