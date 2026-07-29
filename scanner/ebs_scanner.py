"""
scanner/ebs_scanner.py
======================
Scans ALL AWS regions for EBS volumes not attached to any EC2 instance.

Zombie Rule:
    EBS Volume State == 'available' (not attached to any instance)

Multi-region:
    Iterates over all regions returned by get_all_regions().
"""

from __future__ import annotations
import boto3  # type: ignore[import-not-found]
from typing import Optional
import sys
import os
import io

# Force UTF-8 on Windows to avoid charmap codec errors with emoji
# Wrapper removed to prevent crashes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_boto3_kwargs, get_all_regions  # type: ignore[import-not-found]


def _scan_region(region: str) -> list[dict]:
    """
    Scans a single AWS region for unattached EBS volumes.

    Args:
        region: AWS region name (e.g. 'eu-west-1')

    Returns:
        List of resource dicts for all EBS volumes in this region.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))  # type: ignore[operator]
        ec2 = session.client("ec2")

        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate():  # type: ignore
            for volume in page["Volumes"]:
                volume_id = volume["VolumeId"]
                state = volume["State"]          # 'in-use' or 'available'
                size_gb = volume["Size"]
                volume_type = volume["VolumeType"]
                attachments = volume.get("Attachments", [])

                name_tag = next(
                    (t["Value"] for t in volume.get("Tags", []) if t["Key"] == "Name"),
                    "N/A",
                )

                if state == "available":
                    # Volume is unattached → Zombie
                    status = "Zombie"
                    reason = (
                        f"EBS volume is unattached (state=available). "
                        f"Size: {size_gb} GiB, Type: {volume_type}. "
                        f"Wasting ~${size_gb * 0.10:.2f}/month."
                    )
                    utilization = 0.0
                else:
                    attached_to = attachments[0].get("InstanceId", "unknown") if attachments else "unknown"
                    status = "Active"
                    reason = f"Attached to instance: {attached_to}"
                    utilization = 100.0

                icon = "🧟" if status == "Zombie" else "✅"
                print(f"    {icon} {volume_id} ({name_tag}) | "
                      f"{size_gb}GiB {volume_type} | State: {state} | {status}")

                results.append({
                    "resource_id": volume_id,
                    "resource_type": "EBS",
                    "region": region,
                    "utilization": utilization,
                    "status": status,
                    "reason": reason,
                })

    except Exception as e:
        print(f"    ⚠️  Skipping EBS in {region}: {e}")

    return results


def scan_ebs_volumes(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans EBS volumes in each.

    Args:
        regions: List of region names to scan. If None, scans all active regions.

    Returns:
        Combined list of resource dicts from all scanned regions.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning EBS volumes across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} volumes found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ EBS scan complete: {len(all_results)} volumes "
          f"({zombie_total} zombies).")
    return all_results
