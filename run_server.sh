#!/bin/bash
source ~/venv-upgrade/bin/activate
uvicorn web_ui.app:app --host 0.0.0.0 --port 8899 --reload
