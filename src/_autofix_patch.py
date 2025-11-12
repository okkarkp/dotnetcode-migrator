# Add these imports near the top of main.py
from autofix_engine import run_autofix_pipeline, validate_build

# --- Autofix Phase (Layer 2 + 3) ---
print("🚀 Starting autofix pipeline (Layer 2 + 3)...")
fixes = run_autofix_pipeline(tmpdir / "proj", dynamic_rules)
print(f"🧩 Autofix completed for {len(fixes)} rule(s).")

# Validate post-fix build
success, build_log = validate_build(tmpdir / "proj")
if success:
    print("✅ Post-fix build succeeded.")
else:
    print("⚠️ Post-fix build failed; review build_log for details.")
