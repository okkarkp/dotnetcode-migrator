#!/usr/bin/env python3
from pathlib import Path

def write_summary(path: Path,
                  patterns,
                  dyn_rules,
                  results: dict,
                  build_ok: bool,
                  build_log: str):
    total = len(results)
    ok_count = sum(1 for v in results.values() if v)
    fail = [k for k, v in results.items() if not v]
    last_log = (build_log or "")[-1200:]

    md = []
    md.append("## Autofix Results")
    md.append(f"- Rules detected: {len(patterns)}")
    md.append(f"- Dynamic rules generated: {len(dyn_rules)}")
    md.append(f"- Rules attempted: {total}")
    md.append(f"- Rules succeeded: {ok_count}")
    if fail:
        md.append(f"- Rules failed: {len(fail)} → {fail}")
    md.append(f"- Post-fix build status: {'✅ Succeeded' if build_ok else '❌ Failed'}")
    if not build_ok:
        md.append("\n### Build Log (tail)")
        md.append("```")
        md.append(last_log)
        md.append("```")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(md), encoding="utf-8")
# --- improved summarization (deduped & concise) ---
import re, itertools

# merge and deduplicate diagnostics + post-fix logs
merged_text = diag + "\n" + post_fix_log
sentences = re.split(r"(?<=[.!?])\s+", merged_text)
unique_sentences = list(dict.fromkeys(s.strip() for s in sentences if len(s.strip()) > 5))
compressed_diag = " ".join(itertools.islice(unique_sentences, 0, 40))

summary_prompt = f"""
You are a senior .NET migration analyst.
Summarize upgrade actions, fixes applied, and any remaining errors.
Avoid any repetition or paraphrasing. Use short bullet points grouped by theme.

PROJECT INFO:
{json.dumps(project, indent=2)}

RULES (static + dynamic):
{json.dumps(matched + dynamic_rules, indent=2)}

DEDUPED DIAGNOSTICS (trimmed):
{compressed_diag}

POST-FIX STATUS: {"Success" if post_fix_success else "Failed"}
"""
summary = query_llm(summary_prompt, max_tokens=850, temperature=0.25)
if not summary.strip():
    summary = "⚠️ No additional migration recommendations detected."
