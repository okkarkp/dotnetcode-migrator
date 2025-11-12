import pathlib, difflib, os, re

def _suggest_fix(text: str, pattern: str, recommendation: str) -> str:
    # Simple heuristics for common patterns
    if "ConfigurationManager.AppSettings" in pattern or "ConfigurationManager" in pattern:
        # Replace basic AppSettings read with IConfiguration
        text = re.sub(r"ConfigurationManager\.AppSettings\[(.*?)\]",
                      r'new ConfigurationBuilder().AddJsonFile("appsettings.json", optional: true).Build()[\\1]',
                      text)
        if "using Microsoft.Extensions.Configuration;" not in text:
            text = "using Microsoft.Extensions.Configuration;\n" + text
        return text

    if "HttpContext" in pattern:
        # Remove HttpContext usages for console apps
        text = re.sub(r"\bHttpContext\.Current\b", "null /*HttpContext removed*/", text)
        return text

    if "SqlConnection" in pattern:
        text = text.replace("using System.Data.SqlClient", "using Microsoft.Data.SqlClient")
        return text

    # Default: inject a TODO comment near the first occurrence of the token
    token = pattern.split(".")[0]
    return text.replace(token, f"{token} /* TODO: {recommendation} */", 1)

def generate_code_fix(filepath: str, pattern: str, recommendation: str) -> bool:
    p = pathlib.Path(filepath)
    try:
        original = p.read_text(errors="ignore")
    except Exception:
        return False

    updated = _suggest_fix(original, pattern, recommendation)
    if updated == original:
        return False

    # Dry-run?
    dry_run = os.getenv("UPGRADE_DRY_RUN","0") == "1"
    outdir = pathlib.Path(os.getenv("UPGRADE_OUTPUT_DIR","/opt/oss-migrate/upgrade-poc/reports"))
    diffs_dir = outdir / "diffs"
    diffs_dir.mkdir(parents=True, exist_ok=True)

    # Write diff
    diff = difflib.unified_diff(original.splitlines(), updated.splitlines(),
                                fromfile=str(p), tofile=str(p), lineterm="")
    (diffs_dir / (p.name + ".diff")).write_text("\n".join(diff))

    if dry_run:
        print(f"[DRY-RUN] Diff generated for {p}, no write performed")
        return False

    # Backup + write
    p.with_suffix(p.suffix + ".bak")
    p.write_text(updated)
    print(f"✅ AI modified {p} (diff saved)")
    return True
