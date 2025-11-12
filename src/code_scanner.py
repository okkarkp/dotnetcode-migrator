import pathlib, re

def extract_code_sentences(source_dir):
    code_snippets = set()
    for file in pathlib.Path(source_dir).rglob("*.cs"):
        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue
        patterns = [
            r"[A-Z][A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+",
            r"[A-Z][A-Za-z0-9_]+\.[A-Za-z0-9_]+",
            r"[A-Za-z0-9_]+\("
        ]
        for pat in patterns:
            for m in re.findall(pat, text):
                if len(m) > 4 and not m.startswith("using"):
                    code_snippets.add(m.strip("("))
    return sorted(code_snippets)

def scan_code_patterns(source_dir):
    return extract_code_sentences(source_dir)
