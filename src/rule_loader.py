import json, pathlib, re

def load_rules(rule_path):
    rule_path = pathlib.Path(rule_path)
    if not rule_path.exists():
        return []
    try:
        data = json.loads(rule_path.read_text())
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "rules" in data:
            return data["rules"]
    except Exception:
        return []
    return []

def load_static_rules(rule_path):
    return load_rules(rule_path)

def match_rules(packages, rules):
    matched = []
    for pkg, version in packages:
        for r in rules:
            pat = r.get("pattern", "")
            try:
                if re.search(pat, pkg, re.IGNORECASE):
                    matched.append({
                        "id": r.get("id","RULE"),
                        "package": pkg,
                        "currentVersion": version,
                        "issue": r.get("issue"),
                        "recommendation": r.get("recommendation"),
                        "autofix": r.get("autofix", False)
                    })
            except re.error:
                continue
    return matched
