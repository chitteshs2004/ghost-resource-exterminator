"""
scanner/security_group_scanner.py
=================================
Scans ALL AWS regions for custom Security Groups that are not associated
with any active Network Interface (ENI).

Zombie Rule:
    Security Group is not in use by any ENIs AND is not the default security group.
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
    Scans a single AWS region for unused Security Groups.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        ec2 = session.client("ec2")

        # 1. Get all security groups
        sg_response = ec2.describe_security_groups()
        security_groups = sg_response.get("SecurityGroups", [])

        # 2. Get all network interfaces to find active security groups
        eni_paginator = ec2.get_paginator("describe_network_interfaces")
        active_sg_ids = set()
        for page in eni_paginator.paginate():
            for eni in page.get("NetworkInterfaces", []):
                for group in eni.get("Groups", []):
                    active_sg_ids.add(group["GroupId"])

        # 3. Classify each security group
        for sg in security_groups:
            group_id = sg["GroupId"]
            group_name = sg["GroupName"]
            vpc_id = sg.get("VpcId", "N/A")

            # Default security groups cannot/should not be deleted
            if group_name == "default":
                status = "Active"
                reason = "Default security group (protected from deletion)."
                utilization = 100.0
            elif group_id not in active_sg_ids:
                status = "Zombie"
                reason = f"Security Group '{group_name}' in VPC {vpc_id} is not associated with any network interface."
                utilization = 0.0
            else:
                status = "Active"
                reason = f"Security Group is in use by one or more network interfaces."
                utilization = 100.0

            icon = "🧟" if status == "Zombie" else "✅"
            print(f"    {icon} SG: {group_id} ({group_name}) | Status: {status}")

            results.append({
                "resource_id": group_id,
                "resource_type": "SecurityGroup",
                "region": region,
                "utilization": utilization,
                "status": status,
                "reason": reason,
            })

    except Exception as e:
        print(f"    ⚠️  Skipping Security Groups in {region}: {e}")

    return results


def scan_security_groups(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans Security Groups in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning Security Groups across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} security groups found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ Security Group scan complete: {len(all_results)} security groups "
          f"({zombie_total} zombies).")
    return all_results
