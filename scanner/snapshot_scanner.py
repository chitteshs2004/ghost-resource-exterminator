"""
scanner/snapshot_scanner.py
============================
Scans ALL AWS regions for EBS snapshots older than the configured threshold.

Zombie Rule:
    Snapshot.StartTime is older than SNAPSHOT_AGE_DAYS (default 30 days).

Multi-region:
    Iterates over all regions returned by get_all_regions().

Note:
    Each region's snapshots are scoped to OwnerIds=["self"] so we only
    see snapshots owned by this account (not public AWS marketplace AMIs).
"""

from __future__ import annotations
import boto3  # type: ignore[import-not-found]
from datetime import datetime, timedelta, timezone
from typing import Optional
import sys
import os
import io

# Force UTF-8 on Windows to avoid charmap codec errors with emoji
# Wrapper removed to prevent crashes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_boto3_kwargs, get_all_regions, SNAPSHOT_AGE_DAYS  # type: ignore[import-not-found]


def _scan_region(region: str, cutoff_date: datetime) -> list[dict]:
    """
    Scans a single region for old EBS snapshots.

    Args:
        region: AWS region name
        cutoff_date: datetime — snapshots older than this are flagged

    Returns:
        List of resource dicts for all snapshots found in this region.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        ec2 = session.client("ec2")

        paginator = ec2.get_paginator("describe_snapshots")
        for page in paginator.paginate(OwnerIds=["self"]):  # type: ignore
            for snapshot in page["Snapshots"]:
                snapshot_id = snapshot["SnapshotId"]
                start_time = snapshot["StartTime"]
                size_gb = snapshot["VolumeSize"]
                age_days = (datetime.now(timezone.utc) - start_time).days

                name_tag = next(
                    (t["Value"] for t in snapshot.get("Tags", []) if t["Key"] == "Name"),
                    "N/A",
                )

                if start_time < cutoff_date:
                    status = "Zombie"
                    reason = (
                        f"Snapshot is {age_days} days old "
                        f"(threshold: {SNAPSHOT_AGE_DAYS} days). "
                        f"Size: {size_gb} GiB."
                    )
                    utilization = 0.0
                else:
                    status = "Active"
                    reason = f"Snapshot is {age_days} days old — within threshold."
                    utilization = 100.0

                icon = "🧟" if status == "Zombie" else "✅"
                print(f"    {icon} {snapshot_id} | "
                      f"{age_days} days old | {size_gb} GiB | {status}")

                results.append({
                    "resource_id": snapshot_id,
                    "resource_type": "Snapshot",
                    "region": region,
                    "utilization": utilization,
                    "status": status,
                    "reason": reason,
                })

    except Exception as e:
        print(f"    ⚠️  Skipping Snapshots in {region}: {e}")

    return results


def scan_snapshots(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans EBS snapshots in each.

    Args:
        regions: List of region names to scan. If None, scans all active regions.

    Returns:
        Combined list of resource dicts from all scanned regions.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_AGE_DAYS)

    print(f"\n🔍 Scanning EBS snapshots across {len(target_regions)} region(s)...")
    print(f"   Cutoff date: {cutoff_date.strftime('%Y-%m-%d')} ({SNAPSHOT_AGE_DAYS} days ago)")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region, cutoff_date)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} snapshots found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ Snapshot scan complete: {len(all_results)} snapshots "
          f"({zombie_total} zombies).")
    return all_results
