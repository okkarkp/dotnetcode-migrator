#!/usr/bin/env python3
# project_type.py – detect project type from csproj + code

import pathlib, re

def detect_project_type(csproj_path: pathlib.Path):
    text = csproj_path.read_text(errors="ignore")
    code_dir = csproj_path.parent

    if "<Project Sdk=\"Microsoft.NET.Sdk.Web" in text:
        if any("Blazor" in p.name for p in code_dir.rglob("*")):
            return "blazor"
        return "aspnet-webapi"

    if "<Project Sdk=\"Microsoft.NET.Sdk.Razor" in text:
        return "mvc"

    if "<Project Sdk=\"Microsoft.NET.Sdk.Worker" in text:
        return "worker-service"

    if "<Project Sdk=\"Microsoft.NET.Sdk" in text:
        if any("Program.cs" in str(p) for p in code_dir.rglob("*")):
            content = open(next(code_dir.rglob("Program.cs")), "r").read()
            if "WebApplication" in content:
                return "minimal-api"
        return "console-or-library"

    return "unknown"
