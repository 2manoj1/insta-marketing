#!/usr/bin/env python3
"""
Database & OKF Reset Script.
Clears all junk, mock, and unverified data from the system.
Usage:
    uv run python scripts/reset_db.py
    uv run insta-marketing reset
"""
import shutil
import sys
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def reset_all(confirm: bool = True) -> dict:
    """
    Wipes all data stores: SQLite DB, OKF intelligence, leads JSON,
    campaign files, and draft directories.
    Returns a summary dict of what was cleaned.
    """
    summary = {"deleted": [], "skipped": [], "errors": []}

    if confirm:
        print("\n⚠️  This will DELETE all data in:")
        print(f"   • {DATA_DIR / 'leads.db'}")
        print(f"   • {DATA_DIR / 'okf/'}")
        print(f"   • {DATA_DIR / 'drafts/'}")
        print(f"   • {DATA_DIR / 'leads_*.json'}")
        print(f"   • {DATA_DIR / 'campaign_*.json'}")
        print(f"   • {DATA_DIR / 'eval_benchmark_report.json'}")
        answer = input("\nType 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            return summary

    # 1. Delete SQLite database
    db_path = DATA_DIR / "leads.db"
    if db_path.exists():
        try:
            db_path.unlink()
            summary["deleted"].append(str(db_path))
            print(f"  ✓ Deleted {db_path}")
        except Exception as e:
            summary["errors"].append(f"{db_path}: {e}")

    # 2. Reset OKF directory
    okf_dir = DATA_DIR / "okf"
    if okf_dir.exists():
        for f in okf_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                    summary["deleted"].append(str(f))
                    print(f"  ✓ Deleted {f}")
                except Exception as e:
                    summary["errors"].append(f"{f}: {e}")

    # 3. Delete leads JSON files
    for f in DATA_DIR.glob("leads_*.json"):
        try:
            f.unlink()
            summary["deleted"].append(str(f))
            print(f"  ✓ Deleted {f}")
        except Exception as e:
            summary["errors"].append(f"{f}: {e}")

    # 4. Delete campaign JSON files
    for f in DATA_DIR.glob("campaign_*.json"):
        try:
            f.unlink()
            summary["deleted"].append(str(f))
            print(f"  ✓ Deleted {f}")
        except Exception as e:
            summary["errors"].append(f"{f}: {e}")

    # 5. Delete eval benchmark report
    eval_path = DATA_DIR / "eval_benchmark_report.json"
    if eval_path.exists():
        try:
            eval_path.unlink()
            summary["deleted"].append(str(eval_path))
            print(f"  ✓ Deleted {eval_path}")
        except Exception as e:
            summary["errors"].append(f"{eval_path}: {e}")

    # 6. Clear drafts directory
    drafts_dir = DATA_DIR / "drafts"
    if drafts_dir.exists():
        try:
            shutil.rmtree(drafts_dir)
            drafts_dir.mkdir(parents=True, exist_ok=True)
            summary["deleted"].append(str(drafts_dir))
            print(f"  ✓ Cleared {drafts_dir}")
        except Exception as e:
            summary["errors"].append(f"{drafts_dir}: {e}")

    # Recreate clean OKF files
    okf_dir.mkdir(parents=True, exist_ok=True)
    (okf_dir / "brands_intelligence.json").write_text("[]", encoding="utf-8")
    (okf_dir / "creator_memory.json").write_text("{}", encoding="utf-8")
    print(f"  ✓ Recreated clean OKF files")

    print(f"\n✅ Reset complete. Deleted {len(summary['deleted'])} items.")
    if summary["errors"]:
        print(f"⚠️  {len(summary['errors'])} errors occurred:")
        for e in summary["errors"]:
            print(f"   • {e}")

    return summary


if __name__ == "__main__":
    skip_confirm = "--yes" in sys.argv or "--force" in sys.argv
    reset_all(confirm=not skip_confirm)
