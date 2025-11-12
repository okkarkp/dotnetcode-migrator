#!/usr/bin/env python3
# ============================================================
# AI Upgrade Assistant v13 – with Layer 4 Verifier (Bullet-Proof)
# ============================================================

import re, json, sys, shutil, tempfile, subprocess, pathlib, itertools, datetime, traceback, os
from rule_loader import load_rules, match_rules
from dynamic_rules import generate_dynamic_rules
from code_scanner import scan_code_patterns
from llm_client import query_llm
from autofix_engine import run_autofix_pipeline, validate_build
from verifier import verify_and_retry     # 👈 NEW

# ============================================================
#  Argument Parsing (input/output + flags)
# ============================================================

args = sys.argv[1:]
DRY_RUN     = "--dry-run" in args
SAFE_MODE   = "--safe-mode" in args
INPUT_PATH  = pathlib.Path(next((a.split("=",1)[1] for a in args if a.startswith("--input=")),
                                "/opt/oss-migrate/upgrade-poc/sample"))
OUTPUT_PATH = pathlib.Path(next((a.split("=",1)[1] for a in args if a.startswith("--output=")),
                                "/opt/oss-migrate/upgrade-poc/reports"))

RULES  = pathlib.Path("/opt/oss-migrate/upgrade-poc/rules/dotnet_upgrade_rules.json")
SAMPLE = INPUT_PATH / "DemoApp.csproj"
REPORT = OUTPUT_PATH / "upgrade_summary.md"

os.environ["UPGRADE_DRY_RUN"]   = "1" if DRY_RUN else "0"
os.environ["UPGRADE_OUTPUT_DIR"] = str(OUTPUT_PATH)

print(f"🧱 Input: {INPUT_PATH}")
print(f"📦 Output: {OUTPUT_PATH}")
print(f"🧪 Flags: dry_run={DRY_RUN}, safe_mode={SAFE_MODE}")

# ============================================================
#  Helper Functions
# ============================================================

def run_cmd(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return (p.stdout or "") + (p.stderr or "")

def analyze_csproj(path):
    text = pathlib.Path(path).read_text()
    tfm = re.search(r"<TargetFramework>(.*?)</TargetFramework>", text)
    pkgs = re.findall(r'PackageReference Include="(.*?)" Version="(.*?)"', text)
    return {"targetFramework": tfm.group(1) if tfm else None, "packages": pkgs}

def restore_project(csproj):
    return run_cmd(["dotnet","restore",str(csproj)])

def retarget_and_build(csproj_path, target_tfm="net9.0"):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="upgrade_poc_"))
    proj_dir = tmp / "proj"
    shutil.copytree(csproj_path.parent, proj_dir)
    f = proj_dir / csproj_path.name
    t = f.read_text()
    t = re.sub(r"<TargetFramework>.*?</TargetFramework>",
               f"<TargetFramework>{target_tfm}</TargetFramework>", t)
    f.write_text(t)
    restore_project(f)
    diag = run_cmd(["dotnet","build",str(f),"--nologo","-v","m"])
    return diag, tmp

def run_outdated_scan(csproj_path):
    restore_project(csproj_path)
    cmd = ["dotnet","list",str(csproj_path),
           "package","--outdated","--include-transitive","--format","json"]
    return run_cmd(cmd)

def run_runtime_test(tmp_proj_dir):
    try:
        r = subprocess.run(["dotnet","run","--no-build"],
                           cwd=tmp_proj_dir,capture_output=True,text=True,timeout=10)
        print("🧪 Runtime test executed.")
        return r.returncode==0,(r.stdout or r.stderr)[:1000]
    except Exception as e:
        return False,str(e)

def write_report(summary,project,diag,matched,dynamic_rules,
                 code_patterns,outdated_json,fixes_applied,
                 post_fix_success,post_fix_log,runtime_result=None):
    OUTPUT_PATH.mkdir(parents=True,exist_ok=True)
    with open(REPORT,"w") as f:
        f.write("# AI Upgrade Summary (v13 with Verifier)\n\n")
        f.write("## Project Info\n```json\n"+json.dumps(project,indent=2)+"\n```\n\n")
        f.write("## AI-Generated Dynamic Rules\n```json\n"+json.dumps(dynamic_rules,indent=2)+"\n```\n\n")
        f.write("## Matched Static Rules\n```json\n"+json.dumps(matched,indent=2)+"\n```\n\n")
        f.write("## Code Patterns Detected\n```\n"+json.dumps(code_patterns,indent=2)+"\n```\n\n")
        f.write("## Outdated Packages (NuGet)\n```\n"+outdated_json[:3000]+"\n```\n\n")
        f.write("## Build Diagnostics (retargeted)\n```\n"+diag[:2000]+"\n```\n\n")
        f.write("## Autofix Results\n")
        f.write(f"- Rules auto-fixed: {len(fixes_applied)} → {fixes_applied}\n")
        f.write(f"- Post-fix build status: {'✅ Success' if post_fix_success else '❌ Failed'}\n\n")
        f.write("### Post-fix Build Log (first 1200 chars)\n```\n"+(post_fix_log or '')[:1200]+"\n```\n\n")
        if runtime_result:
            ok,log = runtime_result
            f.write("## Runtime Test\n")
            f.write(f"Status: {'✅ Success' if ok else '⚠️ Failed'}\n")
            f.write("```\n"+(log or '')[:1000]+"\n```\n\n")
        f.write("## AI Recommendations\n"+summary+"\n")

def safe_mode_rebuild(tmpdir,rules):
    print("🔁 Safe Mode: reverting AI edits & retrying structured fixes only…")
    for file in pathlib.Path(tmpdir).rglob("*.bak"):
        orig=str(file).replace(".bak","")
        shutil.copyfile(file,orig)
    pkg_rules=[r for r in rules if str(r.get("id","")).startswith("PKG-")]
    from autofix_engine import run_autofix_pipeline,validate_build
    run_autofix_pipeline(tmpdir/"proj",pkg_rules)
    return validate_build(tmpdir/"proj")

# ============================================================
#  Main Orchestrator
# ============================================================

def main():
    if not SAMPLE.exists():
        raise FileNotFoundError(f"Missing csproj at {SAMPLE}")
    project=analyze_csproj(SAMPLE)
    diag,tmpdir=retarget_and_build(SAMPLE,"net9.0")

    try:
        # 1️⃣ Scan
        code_patterns=scan_code_patterns(INPUT_PATH)
        print(f"🧩 Detected {len(code_patterns)} code patterns")

        # 2️⃣ Dynamic rules
        dynamic_rules=generate_dynamic_rules(json.dumps(project,indent=2),diag,code_patterns)
        print(f"🧠 Generated {len(dynamic_rules)} dynamic rules")

        # 3️⃣ Static rules
        static_rules=load_rules(RULES)
        matched=match_rules(project["packages"],static_rules+dynamic_rules)

        # 4️⃣ Outdated packages
        outdated_json=run_outdated_scan(SAMPLE)

        # 5️⃣ Autofix
        print("🚀 Starting autofix pipeline (Layer 2 + 3)…")
        if DRY_RUN:
            print("💡 Dry-run mode active — no writes.")
        fixes_applied=run_autofix_pipeline(tmpdir/"proj",dynamic_rules)
        print(f"🧩 Autofix completed for {len(fixes_applied)} rule(s).")

        # 6️⃣ Build validation (+ Verifier and Safe-Mode)
        post_fix_success,post_fix_log=validate_build(tmpdir/"proj")
        if not post_fix_success:
            print("🧩 Invoking Layer 4 Verifier (post-fix recovery loop)…")
            post_fix_success,post_fix_log=verify_and_retry(tmpdir/"proj")
        if not post_fix_success and SAFE_MODE:
            post_fix_success,post_fix_log=safe_mode_rebuild(tmpdir,dynamic_rules)

        # 7️⃣ Optional runtime test
        runtime_result=None
        if post_fix_success:
            runtime_result=run_runtime_test(tmpdir/"proj")

        # 8️⃣ AI summary
        merged=(diag or '')+"\n"+(post_fix_log or '')
        sentences=re.split(r"(?<=[.!?])\s+",merged)
        unique=list(dict.fromkeys(s.strip() for s in sentences if len(s.strip())>5))
        compressed=" ".join(itertools.islice(unique,0,40))
        summary_prompt=f"""
You are a .NET migration analyst.
Summarize upgrade actions, applied fixes and remaining issues (once only).

PROJECT INFO:
{json.dumps(project,indent=2)}

RULES (static + dynamic):
{json.dumps(matched+dynamic_rules,indent=2)}

DEDUPED DIAGNOSTICS (trimmed):
{compressed}

POST-FIX STATUS: {"Success" if post_fix_success else "Failed"}
"""
        summary=query_llm(summary_prompt,max_tokens=800,temperature=0.25)
        if not summary.strip():
            summary="⚠️ No additional migration recommendations detected."

        # 9️⃣ Report
        write_report(summary,project,diag,matched,dynamic_rules,
                     code_patterns,outdated_json,fixes_applied,
                     post_fix_success,post_fix_log,runtime_result)
        print(f"✅ Report generated: {REPORT}")

    finally:
        shutil.rmtree(tmpdir,ignore_errors=True)

# ============================================================
#  Entrypoint + Exception Guard
# ============================================================

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        crash=OUTPUT_PATH/f"crash_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        crash.parent.mkdir(parents=True,exist_ok=True)
        with open(crash,"w") as f:
            f.write(traceback.format_exc())
        print(f"❌ Unexpected error: {e}\n📄 Trace written to {crash}")
