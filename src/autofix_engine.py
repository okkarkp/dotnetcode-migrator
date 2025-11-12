import subprocess, pathlib, re, os
from autofix_ai import generate_code_fix

def apply_structured_fix(csproj_path: str, rule: dict):
    pattern = rule.get("pattern", "")
    if "Newtonsoft.Json" in pattern:
        subprocess.run(["dotnet", "add", csproj_path, "package", "Newtonsoft.Json", "--version", "13.0.4"])
        print("📦 Upgraded Newtonsoft.Json -> 13.0.4")
        return True
    if "Swashbuckle.AspNetCore" in pattern:
        subprocess.run(["dotnet", "add", csproj_path, "package", "Swashbuckle.AspNetCore", "--version", "9.0.6"])
        print("📦 Upgraded Swashbuckle.AspNetCore -> 9.0.6")
        return True
    if "SqlConnection" in pattern or "System.Data.SqlClient" in pattern or "Microsoft.Data.SqlClient" in pattern:
        subprocess.run(["dotnet", "add", csproj_path, "package", "Microsoft.Data.SqlClient", "--version", "5.2.0"])
        print("📦 Ensured Microsoft.Data.SqlClient -> 5.2.0")
        return True
    return False

def normalize_pattern(text: str):
    text = text.strip().strip("'\"`")
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    for t in ("HttpContext","ConfigurationManager","SqlConnection"):
        if t in tokens: return t
    return tokens[0] if tokens else text

def apply_ai_fix(source_dir: str, rule: dict):
    pattern = normalize_pattern(rule.get("pattern",""))
    rec = rule.get("recommendation","")
    print(f"🧠 AI autofix for '{pattern}'")
    changed = False
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue
        if pattern in text:
            changed |= generate_code_fix(str(file), pattern, rec)
    return changed

def apply_universal_ai_fix(source_dir: str, rule: dict, skip_if_changed: bool):
    if skip_if_changed:
        return False
    pattern = normalize_pattern(rule.get("pattern",""))
    rec = rule.get("recommendation","")
    changed = False
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue
        if pattern in text:
            print(f"🧠 Universal AI autofix for '{pattern}' in {file.name}")
            changed |= generate_code_fix(str(file), pattern, rec)
    return changed

def ensure_configuration_reference(csproj_path: str, source_dir: str):
    found = False
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        text = file.read_text(errors="ignore")
        if "IConfiguration" in text or "ConfigurationBuilder" in text:
            found = True; break
    if found:
        print("📦 Adding Microsoft.Extensions.Configuration packages...")
        subprocess.run(["dotnet","add",csproj_path,"package","Microsoft.Extensions.Configuration","--version","9.0.0"])
        subprocess.run(["dotnet","add",csproj_path,"package","Microsoft.Extensions.Configuration.Json","--version","9.0.0"])
        subprocess.run(["dotnet","add",csproj_path,"package","Microsoft.Extensions.Configuration.Binder","--version","9.0.0"])
        return True
    return False

def ensure_sqlclient_reference_and_namespace(csproj_path: str, source_dir: str):
    add_pkg = False
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        text = file.read_text(errors="ignore")
        if "SqlConnection" in text or "System.Data.SqlClient" in text or "Microsoft.Data.SqlClient" in text:
            add_pkg = True
            if "using System.Data.SqlClient" in text:
                new = text.replace("using System.Data.SqlClient","using Microsoft.Data.SqlClient")
                if new != text:
                    file.write_text(new)
                    print(f"🔁 Namespace migrated in {file.name}: System.Data.SqlClient -> Microsoft.Data.SqlClient")
    if add_pkg:
        subprocess.run(["dotnet","add",csproj_path,"package","Microsoft.Data.SqlClient","--version","5.2.0"])
        print("📦 Ensured Microsoft.Data.SqlClient package")
        return True
    return False

def ensure_aspnet_http_abstractions(csproj_path: str, source_dir: str):
    need = False
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        text = file.read_text(errors="ignore")
        if "IHttpContextAccessor" in text:
            need = True; break
    if need:
        print("📦 Adding Microsoft.AspNetCore.Http.Abstractions for IHttpContextAccessor")
        subprocess.run(["dotnet","add",csproj_path,"package","Microsoft.AspNetCore.Http.Abstractions","--version","2.2.0"])
        return True
    return False

def ensure_usings_if_missing(source_dir: str):
    candidates = {
        "IConfiguration": "using Microsoft.Extensions.Configuration;",
        "ConfigurationBuilder": "using Microsoft.Extensions.Configuration;",
        "SqlConnection": "using Microsoft.Data.SqlClient;"
    }
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        text = file.read_text(errors="ignore")
        updated = text
        for key, using_line in candidates.items():
            if key in text and using_line not in text:
                lines = updated.splitlines()
                insert_at = 0
                for i, ln in enumerate(lines[:20]):
                    if ln.startswith("using "): insert_at = i + 1
                lines.insert(insert_at, using_line)
                updated = "\n".join(lines)
        if updated != text:
            file.write_text(updated)
            print(f"➕ Usings injected in {file.name}")

def patch_invalid_web_contexts(source_dir: str):
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        text = file.read_text(errors="ignore")
        new = text
        new = re.sub(r"\bHttpContext\.Current\b","null /*HttpContext removed for console*/", new)
        new = re.sub(r"\bnew\s+HttpContext\s*\([^)]*\)","null /*HttpContext stub*/", new)
        new = re.sub(r"\bIHttpContextAccessor\b","/*HttpContext removed*/object", new)
        new = re.sub(r"using\s+Microsoft\.AspNetCore\.[^\n]+","// removed AspNetCore using for console build", new)
        if new != text:
            file.write_text(new)
            print(f"🩹 Patched web-only context in {file.name}")

def run_autofix_pipeline(tmp_proj_dir: str, rules: list):
    csproj = next(pathlib.Path(tmp_proj_dir).rglob("*.csproj"))
    source_dir = tmp_proj_dir
    fixes_applied = []
    for r in rules:
        if not r.get("autofix"): continue
        fixed = False
        fixed |= apply_structured_fix(str(csproj), r)
        changed_once = apply_ai_fix(source_dir, r)
        fixed |= changed_once
        fixed |= apply_universal_ai_fix(source_dir, r, skip_if_changed=changed_once)
        if fixed:
            fixes_applied.append(r["id"])
    print(f"✅ Applied {len(fixes_applied)} autofix(es): {fixes_applied}")

    ensure_configuration_reference(str(csproj), source_dir)
    ensure_sqlclient_reference_and_namespace(str(csproj), source_dir)
    ensure_aspnet_http_abstractions(str(csproj), source_dir)
    ensure_usings_if_missing(source_dir)
    patch_invalid_web_contexts(source_dir)
    return fixes_applied

def validate_build(tmp_proj_dir: str):
    result = subprocess.run(
        ["dotnet","build",str(tmp_proj_dir),"--nologo","-v","m"],
        capture_output=True, text=True
    )
    success = result.returncode == 0
    print("✅ Build succeeded after fixes" if success else "❌ Build failed after fixes")
    return success, (result.stdout or result.stderr)[:2000]
