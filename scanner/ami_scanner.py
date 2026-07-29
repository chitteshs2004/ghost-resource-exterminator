"""
scanner/ami_scanner.py
======================
Scans ALL AWS regions for custom AMIs (Amazon Machine Images) owned by the account
that are not currently referenced by any active/stopped EC2 instances.

Zombie Rule:
    AMI belongs to OwnerIds=['self'] AND is not in use by any non-terminated instances.
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
    Scans a single AWS region for unused AMIs.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        ec2 = session.client("ec2")

        # 1. Fetch custom AMIs
        images_response = ec2.describe_images(Owners=["self"])
        images = images_response.get("Images", [])

        if not images:
            return results

        # 2. Fetch all instances to check which AMIs are in use
        active_ami_ids = set()
        instance_paginator = ec2.get_paginator("describe_instances")
        for page in instance_paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    if instance["State"]["Name"] != "terminated":
                        active_ami_ids.add(instance.get("ImageId"))

        # 3. Classify custom AMIs
        for img in images:
            image_id = img["ImageId"]
            name = img.get("Name", "N/A")

            if image_id not in active_ami_ids:
                status = "Zombie"
                reason = f"Custom AMI '{name}' is not used by any active or stopped EC2 instances."
                utilization = 0.0
            else:
                status = "Active"
                reason = "Custom AMI is associated with active instance(s)."
                utilization = 100.0

            icon = "🧟" if status == "Zombie" else "✅"
            print(f"    {icon} AMI: {image_id} ({name}) | Status: {status}")

            results.append({
                "resource_id": image_id,
                "resource_type": "AMI",
                "region": region,
                "utilization": utilization,
                "status": status,
                "reason": reason,
            })

    except Exception as e:
        print(f"    ⚠️  Skipping AMIs in {region}: {e}")

    return results


def scan_amis(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans AMIs in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning AMIs across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} AMIs found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ AMI scan complete: {len(all_results)} AMIs "
          f"({zombie_total} zombies).")
    return all_results
