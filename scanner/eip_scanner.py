"""
scanner/eip_scanner.py
======================
Scans ALL AWS regions for Elastic IPs (EIPs) that are not associated
with any running instance or network interface (ENI).

Zombie Rule:
    EIP has no 'AssociationId' or 'InstanceId'.
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
    Scans a single AWS region for unused Elastic IPs.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        ec2 = session.client("ec2")

        # Describe all EIP addresses
        response = ec2.describe_addresses()
        for address in response.get("Addresses", []):
            public_ip = address.get("PublicIp", "N/A")
            association_id = address.get("AssociationId")
            allocation_id = address.get("AllocationId")

            # A unique resource ID is required; use AllocationId, fallback to PublicIp
            resource_id = allocation_id or public_ip

            name_tag = next(
                (t["Value"] for t in address.get("Tags", []) if t["Key"] == "Name"),
                "N/A",
            )

            if not association_id:
                # EIP is unused -> Zombie
                status = "Zombie"
                reason = f"Elastic IP {public_ip} is not associated with any instance or ENI. Wasting ~$3.60/month."
                utilization = 0.0
            else:
                status = "Active"
                reason = f"Associated with ENI/Instance (Association ID: {association_id})"
                utilization = 100.0

            icon = "🧟" if status == "Zombie" else "✅"
            print(f"    {icon} {public_ip} | Allocation ID: {allocation_id} | Status: {status}")

            results.append({
                "resource_id": resource_id,
                "resource_type": "EIP",
                "region": region,
                "utilization": utilization,
                "status": status,
                "reason": reason,
            })

    except Exception as e:
        print(f"    ⚠️  Skipping EIPs in {region}: {e}")

    return results


def scan_eips(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans EIPs in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning Elastic IPs across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} EIPs found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ EIP scan complete: {len(all_results)} EIPs "
          f"({zombie_total} zombies).")
    return all_results
