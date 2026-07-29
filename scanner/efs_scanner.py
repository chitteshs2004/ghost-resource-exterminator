"""
scanner/efs_scanner.py
======================
Scans ALL AWS regions for EFS (Elastic File System) file systems that are orphaned (have 0 mount targets).

Zombie Rule:
    EFS File System has 0 mount targets.
"""

from __future__ import annotations
import boto3  # type: ignore[import-not-found]
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_boto3_kwargs, get_all_regions  # type: ignore[import-not-found]


def _scan_region(region: str) -> list[dict]:
    """
    Scans a single AWS region for orphaned EFS file systems.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        efs = session.client("efs")

        # Describe all EFS file systems
        response = efs.describe_file_systems()
        for fs in response.get("FileSystems", []):
            fs_id = fs["FileSystemId"]
            name = fs.get("Name", "N/A")
            num_mount_targets = fs.get("NumberOfMountTargets", 0)

            if num_mount_targets == 0:
                status = "Zombie"
                reason = "EFS File System has 0 mount targets (orphaned/unmounted)."
                utilization = 0.0
            else:
                status = "Active"
                reason = f"EFS File System has {num_mount_targets} mount target(s)."
                utilization = 100.0

            icon = "🧟" if status == "Zombie" else "✅"
            print(f"    {icon} EFS: {fs_id} ({name}) | Mount Targets: {num_mount_targets} | Status: {status}")

            results.append({
                "resource_id": fs_id,
                "resource_type": "EFS",
                "region": region,
                "utilization": utilization,
                "status": status,
                "reason": reason,
            })

    except Exception as e:
        # Some regions may not support EFS or require opt-in
        print(f"    ⚠️  Skipping EFS in {region}: {e}")

    return results


def scan_efs(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans EFS file systems in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning EFS File Systems across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} file systems found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ EFS scan complete: {len(all_results)} EFS file systems "
          f"({zombie_total} zombies).")
    return all_results
