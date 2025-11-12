# 🧠 dotnetcode-migrator

An AI-assisted, offline .NET code upgrade assistant — built to automatically scan, reason, and migrate .NET projects between framework versions (e.g., 6 → 8 → 9).

### 🚀 Features
- Offline LLM (Phi-4 Mini or TinyLlama) reasoning
- Automatic rule generation and code autofix
- Safe-mode rollback and dry-run preview
- Integrated `dotnet` build/test validation

### ⚙️ Usage

```bash
# Dry run (preview only)
python3 main.py --dry-run --input=sample --output=reports

# Full upgrade (auto rollback if fails)
python3 main.py --safe-mode --input=sample --output=reports

