import shutil

def safe_mode_rebuild(tmpdir, rules):
    print("🔁 Safe mode: reverting AI edits and retrying with structured fixes only…")
    for file in pathlib.Path(tmpdir).rglob("*.bak"):
        orig = str(file).replace(".bak", "")
        shutil.copyfile(file, orig)
    fixes = [r for r in rules if r["id"].startswith("PKG-")]
    from autofix_engine import run_autofix_pipeline, validate_build
    run_autofix_pipeline(tmpdir / "proj", fixes)
    return validate_build(tmpdir / "proj")
