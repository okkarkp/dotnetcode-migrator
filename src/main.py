#!/usr/bin/env python3
# AI Upgrade Orchestrator – Production v21 (Rule Decay + Project Type + Confidence)

import re, json, sys, shutil, tempfile, pathlib, datetime, traceback, os
from rule_loader import load_rules, match_rules
from dynamic_rules import generate_dynamic_rules
from code_scanner import scan_code_patterns
from autofix_engine import run_autofix_pipeline, validate_build
from verifier import verify_and_retry
from utils import run_cmd, list_csprojs, extract_error_codes, has_build_success
from learning_db import log_rule_result
from project_type import detect_project_type
from llm_client import query_llm

# -------------------------------------------------------------------------
# Arguments
# -------------------------------------------------------------------------
args = sys.argv[1:]

DRY_RUN   = "--dry-run" in args
SAFE_MODE = "--safe-mode" in args
INPUT     = pathlib.Path(next((a.split("=",1)[1] for a in args if a.startswith("--input=")), "."))
OUTPUT    = pathlib.Path(next((a.split("=",1)[1] for a in args if a.startswith("--output=")), "./reports"))
TARGET_TFM = next((a.split("=",1)[1] for a in args if a.startswith("--target=")), "net9.0")

print(f"🧱 Input: {INPUT}")
print(f"📦 Output: {OUTPUT}")
print(f"🎯 Target: {TARGET_TFM}")
print(f"🧪 Flags: dry_run={DRY_RUN}, safe_mode={SAFE_MODE}")

OUTPUT.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------------------
# Discover .csproj files
# -------------------------------------------------------------------------
csproj_files = list_csprojs(INPUT)
if not csproj_files:
    raise FileNotFoundError(f"No .csproj files under {INPUT}")

print(f"🧩 Found {len(csproj_files)} project(s):")
for f in csproj_files:
    print(f"   • {f}")

# -------------------------------------------------------------------------
# Dependency ordering
# -------------------------------------------------------------------------
def sort_by_dependencies(files):
    dep_map = {}
    for proj in files:
        txt = pathlib.Path(proj).read_text(errors="ignore")
        refs = re.findall(r'<ProjectReference Include="(.*?)"', txt)
        deps = [str((pathlib.Path(proj).parent / r).resolve()) for r in refs]
        dep_map[str(proj)] = deps

    order, seen = [], set()

    def dfs(node):
        if node in seen: return
        for dep in dep_map.get(node, []):
            if dep in dep_map:
                dfs(dep)
        seen.add(node)
        order.append(node)

    for f in map(str, files):
        dfs(f)

    return [pathlib.Path(p) for p in order if pathlib.Path(p) in files] or files

# -------------------------------------------------------------------------
# Analyze csproj
# -------------------------------------------------------------------------
def analyze_csproj(path):
    t = pathlib.Path(path).read_text()
    tfm = re.search(r"<TargetFramework>(.*?)</TargetFramework>", t)
    pkgs = re.findall(r'PackageReference Include="(.*?)" Version="(.*?)"', t)
    return {"targetFramework": tfm.group(1) if tfm else None, "packages": pkgs}

# -------------------------------------------------------------------------
# Retarget + initial build
# -------------------------------------------------------------------------
def retarget_and_build(csproj_path, target_tfm=TARGET_TFM):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="upgrade_poc_"))
    proj_dir = tmp / "proj"
    shutil.copytree(csproj_path.parent, proj_dir)

    f = proj_dir / csproj_path.name
    txt = f.read_text()
    txt = re.sub(r"<TargetFramework>.*?</TargetFramework>",
                 f"<TargetFramework>{target_tfm}</TargetFramework>", txt)
    f.write_text(txt)

    run_cmd(["dotnet","restore"], cwd=proj_dir)
    diag = run_cmd(["dotnet","build","--nologo","-v","m"], cwd=proj_dir)
    return diag, tmp

# -------------------------------------------------------------------------
# Outdated scan
# -------------------------------------------------------------------------
def run_outdated_scan(csproj_path):
    run_cmd(["dotnet","restore",str(csproj_path)])
    return run_cmd(["dotnet","list",str(csproj_path),"package",
                    "--outdated","--include-transitive","--format","json"])

# -------------------------------------------------------------------------
# Write final report
# -------------------------------------------------------------------------
def write_report(report_path, summary_txt, project, diag, matched,
                 dynamic_rules, patterns, outdated_json,
                 fixes, post_ok, post_log, project_type):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# Upgrade Report – Production v21\n\n")
        f.write(f"## Target Framework: {TARGET_TFM}\n\n")
        f.write(f"## Project Type: {project_type}\n\n")

        f.write("## Project Info\n```json\n")
        f.write(json.dumps(project, indent=2))
        f.write("\n```\n\n")

        f.write("## Dynamic Rules (AI + Memory)\n```json\n")
        f.write(json.dumps(dynamic_rules, indent=2))
        f.write("\n```\n\n")

        f.write("## Matched Static + Dynamic Rules\n```json\n")
        f.write(json.dumps(matched, indent=2))
        f.write("\n```\n\n")

        f.write("## Code Patterns\n```json\n")
        f.write(json.dumps(patterns, indent=2))
        f.write("\n```\n\n")

        f.write("## Outdated Packages\n```\n")
        f.write((outdated_json or "")[:3000])
        f.write("\n```\n\n")

        f.write("## Initial Diagnostics\n```\n")
        f.write((diag or "")[:2000])
        f.write("\n```\n\n")

        f.write("## Autofix Results\n")
        f.write(f"- Rules auto-fixed: {len(fixes)} → {fixes}\n")
        f.write(f"- Post-fix build: {'✅ SUCCESS' if post_ok else '❌ FAILED'}\n\n")

        f.write("### Post-Fix Build Log\n```\n")
        f.write((post_log or "")[:2000])
        f.write("\n```\n\n")

        f.write("## AI Summary\n")
        f.write(summary_txt)
        f.write("\n")

# -------------------------------------------------------------------------
# Process each project
# -------------------------------------------------------------------------
for sample in sort_by_dependencies(csproj_files):
    tmpdir = None
    try:
        print(f"\n🚀 Processing project: {sample.name}")
        REPORT = OUTPUT / f"{sample.stem}_upgrade_summary.md"

        # 1. Detect project type
        project_type = detect_project_type(sample)
        print(f"📌 Project Type: {project_type}")

        # 2. Analyze project
        project = analyze_csproj(sample)

        # 3. Retarget + initial build
        diag, tmpdir = retarget_and_build(sample, TARGET_TFM)

        # 4. Code patterns
        patterns = scan_code_patterns(sample.parent)
        print(f"🧩 Code patterns found: {len(patterns)}")

        # 5. AI + memory dynamic rules
        dynamic_rules = generate_dynamic_rules(
            json.dumps(project, indent=2),
            diag,
            patterns,
            csproj_path=sample
        )
        print(f"🧠 Dynamic rules: {len(dynamic_rules)}")

        # 6. Static rules
        static_rules = load_rules("/opt/oss-migrate/upgrade-poc/rules/dotnet_upgrade_rules.json")
        matched = match_rules(project["packages"], static_rules + dynamic_rules)

        # 7. Outdated packages
        outdated_json = run_outdated_scan(sample)

        # 8. Autofix pipeline
        print("🔧 Running autofix pipeline…")
        fixes = run_autofix_pipeline(tmpdir/"proj", dynamic_rules)

        # 9. Post fix build
        post_ok, post_log = validate_build(tmpdir/"proj")
        if not post_ok:
            print("🔍 Running verifier…")
            post_ok, post_log = verify_and_retry(tmpdir/"proj")

        # 10. Log-learning to SQLite
        for r in dynamic_rules:
            log_rule_result(
                r.get("id"),
                r.get("pattern"),
                r.get("recommendation"),
                sample.stem,
                extract_error_codes(post_log),
                post_ok,
                r.get("confidence", 1.0)
            )

        # 11. AI summary
        combined = (diag or "") + "\n" + (post_log or "")
        summary = query_llm(
            f"Summarize migration actions and issues:\n{combined[:4000]}",
            max_tokens=450, temperature=0.2
        ) or "—"

        # 12. Report
        write_report(
            REPORT, summary, project, diag, matched,
            dynamic_rules, patterns, outdated_json,
            fixes, post_ok, post_log, project_type
        )

        print(f"✅ Done: {REPORT}")

    except Exception as e:
        crash = OUTPUT / f"crash_{sample.stem}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(crash, "w") as f:
            f.write(traceback.format_exc())
        print(f"❌ Error: {e}\n📄 Crash log saved: {crash}")

    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
