#!/usr/bin/env python3
"""
Root proxy CLI script for knowledge ingestion.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "scripts" else Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import main from backend/scripts/ingest.py
from backend.scripts.ingest import main

if __name__ == "__main__":
    main()
