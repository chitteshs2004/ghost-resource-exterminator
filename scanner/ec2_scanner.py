"""
scanner/ec2_scanner.py
======================
Scans ALL AWS regions for EC2 instances and fetches their average CPU
utilization from CloudWatch over the last 7 days.

Zombie Rule:
    Average CPUUtilization < EC2_CPU_ZOMBIE_THRESHOLD (default 1%)
    over the past CLOUDWATCH_DAYS (default 7) days.

Multi-region:
    Calls get_all_regions() from config to discover every active region,
    then scans each one independently.
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

from config import get_boto3_kwargs, get_all_regions, EC2_CPU_ZOMBIE_THRESHOLD, CLOUDWATCH_DAYS  # type: ignore[import-not-found]


def _get_avg_cpu(cloudwatch, instance_id: str, days: int) -> float:
    """
    Queries CloudWatch for the average CPUUtilization of a given EC2 instance
    over the specified number of days.

    Returns average CPU utilization as a float (0.0 if no data available).
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    try:
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=now,
            Period=86400,       # 1-day granularity (in seconds)
            Statistics=["Average"],
            Unit="Percent",
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return 0.0
        avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
        return round(float(avg_cpu), 4)  # type: ignore[return-value]

    except Exception as e:
        print(f"    ⚠️  CloudWatch error for {instance_id}: {e}")
        return 0.0


def _scan_region(region: str) -> list[dict]:
    """
    Scans a single AWS region for EC2 instances and evaluates zombie status.

    Args:
        region: AWS region name (e.g. 'us-east-1')

    Returns:
        List of resource dicts for all non-terminated instances in the region.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))  # type: ignore[operator]
        ec2 = session.client("ec2")
        cloudwatch = session.client("cloudwatch")

        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():  # type: ignore
            for reservation in page["Reservations"]:  # type: ignore
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    state = instance["State"]["Name"]

                    if state != "running":
                        continue

                    avg_cpu = _get_avg_cpu(cloudwatch, instance_id, CLOUDWATCH_DAYS)

                    if avg_cpu < EC2_CPU_ZOMBIE_THRESHOLD:
                        status = "Zombie"
                        reason = (
                            f"Avg CPU {avg_cpu:.2f}% over {CLOUDWATCH_DAYS} days "
                            f"(threshold: {EC2_CPU_ZOMBIE_THRESHOLD}%)"
                        )
                    else:
                        status = "Active"
                        reason = f"Avg CPU {avg_cpu:.2f}% — within normal range"

                    name_tag = next(
                        (t["Value"] for t in instance.get("Tags", []) if t["Key"] == "Name"),
                        "N/A",
                    )

                    icon = "🧟" if status == "Zombie" else "✅"
                    print(f"    {icon} {instance_id} ({name_tag}) | "
                          f"State: {state} | CPU: {avg_cpu:.2f}% | {status}")

                    results.append({
                        "resource_id": instance_id,
                        "resource_type": "EC2",
                        "region": region,
                        "utilization": avg_cpu,
                        "status": status,
                        "reason": reason,
                    })

    except Exception as e:
        # Some regions may not support EC2 or may be inaccessible
        print(f"    ⚠️  Skipping EC2 in {region}: {e}")

    return results


def scan_ec2_instances(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans EC2 instances in each.

    Args:
        regions: List of region names to scan. If None, scans all active regions.

    Returns:
        Combined list of resource dicts from all scanned regions.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning EC2 instances across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} instances found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ EC2 scan complete: {len(all_results)} instances "
          f"({zombie_total} zombies).")
    return all_results
