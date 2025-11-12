import subprocess

def run_outdated_scan(csproj_path):
    """Run restore automatically before scanning."""
    try:
        subprocess.run(["dotnet", "restore", str(csproj_path)], check=True, text=True)
    except Exception as e:
        print("⚠️ Restore failed:", e)

    cmd = [
        "dotnet", "list", str(csproj_path),
        "package", "--outdated", "--include-transitive", "--format", "json"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return result.stdout.strip()
    except Exception as e:
        return f"error running dotnet list package: {e}"
