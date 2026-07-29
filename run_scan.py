"""
run_scan.py
===========
CLI entry point for Ghost Resource Exterminator.

Run this script to trigger a full scan of your real AWS account
and populate the SQLite database with zombie resource data.

Usage:
    python run_scan.py                          # Full live scan (all regions)
    python run_scan.py --region us-east-1       # Scan specific region
    python run_scan.py --cleanup                # Scan then offer cleanup (DRY RUN)
"""

import sys
import os
import utf8_fix  # noqa: F401

# Ensure parent directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_with_cleanup(resource_types=None):
    """Run scan then offer dry-run cleanup."""
    from zombie_detector import scan_all  # type: ignore[import-not-found]
    from cleanup import cleanup_all_zombies  # type: ignore[import-not-found]
    scan_all(clear_before_scan=True, resource_types=resource_types)
    print("\n" + "=" * 60)
    print("🧹 Starting cleanup in DRY RUN mode (no resources deleted)...")
    cleanup_all_zombies(dry_run=True, resource_types=resource_types)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]  # type: ignore

    # Parse --region flag (accepts single or comma-separated)
    # Example: python run_scan.py --region us-east-1
    # Example: python run_scan.py --region us-east-1,ap-south-1
    scan_regions = None
    if "--region" in args:
        idx = args.index("--region")
        if idx + 1 < len(args):
            raw: str = args[idx + 1]
            scan_regions = [r.strip() for r in raw.split(",") if r.strip()]
            print(f"📍 Region filter: {', '.join(scan_regions)}")
        else:
            print("❌ --region requires a value, e.g.: python run_scan.py --region us-east-1")
            sys.exit(1)

    # Parse --type flag (accepts single or comma-separated)
    # Example: python run_scan.py --type EC2,SecurityGroup
    scan_types = None
    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 < len(args):
            raw: str = args[idx + 1]
            scan_types = [t.strip() for t in raw.split(",") if t.strip()]
            print(f"🔍 Resource type filter: {', '.join(scan_types)}")
        else:
            print("❌ --type requires a value, e.g.: python run_scan.py --type EC2,SecurityGroup")
            sys.exit(1)

    if "--cleanup" in args:
        run_with_cleanup(resource_types=scan_types)
    else:
        from zombie_detector import scan_all  # type: ignore[import-not-found]
        scan_all(clear_before_scan=True, regions=scan_regions, resource_types=scan_types)
