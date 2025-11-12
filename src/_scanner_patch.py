# --- correct code scanner import + call for main.py ---

# near top of main.py
from code_scanner import extract_code_sentences

# inside main(), use:
source_dir = ROOT / "sample"
code_patterns = extract_code_sentences(source_dir)
print(f"🧩 Detected {len(code_patterns)} code patterns")
