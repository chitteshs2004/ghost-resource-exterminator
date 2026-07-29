"""
scanner/stopped_ec2_scanner.py
==============================
Scans ALL AWS regions for EC2 instances that are currently in a 'stopped' state.

Zombie Rule:
    Instance state is 'stopped'.
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
    Scans a single AWS region for stopped EC2 instances.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        ec2 = session.client("ec2")

        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    state = instance["State"]["Name"]

                    if state == "stopped":
                        status = "Zombie"
                        name_tag = next(
                            (t["Value"] for t in instance.get("Tags", []) if t["Key"] == "Name"),
                            "N/A",
                        )
                        reason = f"EC2 Instance is in stopped state. Costing money for underlying EBS volume storage."
                        utilization = 0.0

                        icon = "🧟"
                        print(f"    {icon} Stopped Instance: {instance_id} ({name_tag}) | Status: {status}")

                        results.append({
                            "resource_id": instance_id,
                            "resource_type": "StoppedEC2",
                            "region": region,
                            "utilization": utilization,
                            "status": status,
                            "reason": reason,
                        })

    except Exception as e:
        print(f"    ⚠️  Skipping Stopped EC2 in {region}: {e}")

    return results


def scan_stopped_ec2(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans stopped EC2 instances in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning Stopped EC2 instances across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} stopped instances found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ Stopped EC2 scan complete: {len(all_results)} instances "
          f"({zombie_total} zombies).")
    return all_results
