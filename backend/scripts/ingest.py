#!/usr/bin/env python3
"""
CLI Ingestion Script

Usage:
  python -m backend.scripts.ingest --pdf data/ml.pdf --role "Machine Learning Engineer"
  python scripts/ingest.py --pdf data/ml.pdf --role "Machine Learning Engineer" --source "Tom Mitchell ML" --force
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure backend directory is in Python path for absolute imports
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR
ROOT_DIR = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app.services.ingestion import ingest_pdf
except ImportError:
    # If called from root without package hierarchy
    from backend.app.services.ingestion import ingest_pdf


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest role-specific knowledge base PDFs into ChromaDB with embeddings."
    )
    parser.add_argument(
        "--pdf", "-p",
        required=True,
        type=str,
        help="Path to the PDF file (e.g. data/tom_mitchell_ml.pdf)"
    )
    parser.add_argument(
        "--role", "-r",
        required=True,
        type=str,
        help="Target candidate role (e.g. 'Machine Learning Engineer', 'Backend Engineer')"
    )
    parser.add_argument(
        "--source", "-s",
        type=str,
        default=None,
        help="Custom source textbook/document title (default: derived from filename)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        default=False,
        help="Force re-ingestion and overwrite if document already exists in vector store"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_absolute():
        # Check relative to current working directory or ROOT_DIR
        candidate_paths = [
            Path.cwd() / args.pdf,
            ROOT_DIR / args.pdf,
            BACKEND_DIR / args.pdf
        ]
        for p in candidate_paths:
            if p.exists():
                pdf_path = p
                break

    if not pdf_path.exists():
        print(f"\n[ERROR] PDF file not found at: {args.pdf}")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  AI Role-Based Screening: Knowledge Ingestion")
    print(f"=======================================================")
    print(f"  File:        {pdf_path}")
    print(f"  Role:        {args.role}")
    print(f"  Source Book: {args.source or pdf_path.stem.title()}")
    print(f"  Force Mode:  {args.force}")
    print(f"=======================================================\n")

    try:
        result = ingest_pdf(
            pdf_path=str(pdf_path),
            role=args.role,
            source_book=args.source,
            force=args.force
        )

        print("\n-------------------------------------------------------")
        print(" Ingestion Summary Result:")
        print("-------------------------------------------------------")
        for k, v in result.items():
            print(f"  • {k}: {v}")
        print("-------------------------------------------------------\n")

        if result.get("status") == "skipped":
            print("[INFO] Document was skipped because it was already ingested.")
            print("[INFO] Use --force flag if you wish to overwrite.")
        elif result.get("status") == "success":
            print("[SUCCESS] PDF knowledge base successfully ingested into ChromaDB!")

    except Exception as e:
        print(f"\n[FATAL ERROR] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
