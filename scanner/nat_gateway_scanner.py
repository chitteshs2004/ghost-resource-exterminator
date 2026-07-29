"""
scanner/nat_gateway_scanner.py
==============================
Scans ALL AWS regions for NAT Gateways and checks their traffic/connection metrics in CloudWatch.

Zombie Rule:
    NAT Gateway state is 'available' AND has 0 active connections / traffic over last CLOUDWATCH_DAYS days.
"""

from __future__ import annotations
import boto3  # type: ignore[import-not-found]
from datetime import datetime, timedelta, timezone
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_boto3_kwargs, get_all_regions, CLOUDWATCH_DAYS  # type: ignore[import-not-found]


def _get_nat_traffic(cloudwatch, gateway_id: str, days: int) -> float:
    """
    Queries CloudWatch for the sum of ActiveConnectionCount for a NAT Gateway.
    If that returns no data, we fallback to BytesInFromSource to see if there is any traffic.
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    try:
        # Check connection count
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/NATGateway",
            MetricName="ActiveConnectionCount",
            Dimensions=[{"Name": "NatGatewayId", "Value": gateway_id}],
            StartTime=start_time,
            EndTime=now,
            Period=86400,
            Statistics=["Sum"],
        )
        datapoints = response.get("Datapoints", [])
        if datapoints:
            return float(sum(dp["Sum"] for dp in datapoints))

        # Fallback to BytesInFromSource
        response_bytes = cloudwatch.get_metric_statistics(
            Namespace="AWS/NATGateway",
            MetricName="BytesInFromSource",
            Dimensions=[{"Name": "NatGatewayId", "Value": gateway_id}],
            StartTime=start_time,
            EndTime=now,
            Period=86400,
            Statistics=["Sum"],
        )
        datapoints_bytes = response_bytes.get("Datapoints", [])
        if datapoints_bytes:
            return float(sum(dp["Sum"] for dp in datapoints_bytes))

        return 0.0
    except Exception:
        # If CloudWatch query fails, default to -1.0 (unknown)
        return -1.0


def _scan_region(region: str) -> list[dict]:
    """
    Scans a single AWS region for idle NAT Gateways.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        ec2 = session.client("ec2")
        cloudwatch = session.client("cloudwatch")

        response = ec2.describe_nat_gateways()
        for gw in response.get("NatGateways", []):
            gw_id = gw["NatGatewayId"]
            state = gw["State"]

            if state != "available":
                continue

            vpc_id = gw.get("VpcId", "N/A")
            traffic = _get_nat_traffic(cloudwatch, gw_id, CLOUDWATCH_DAYS)

            if traffic == 0.0:
                status = "Zombie"
                reason = f"NAT Gateway in VPC {vpc_id} has 0 connections or traffic over the last {CLOUDWATCH_DAYS} days. Wasting ~$32.00/month."
                utilization = 0.0
            else:
                status = "Active"
                reason = f"NAT Gateway has active traffic/connections."
                utilization = 100.0

            icon = "🧟" if status == "Zombie" else "✅"
            print(f"    {icon} NAT Gateway: {gw_id} | Traffic Index: {traffic} | Status: {status}")

            results.append({
                "resource_id": gw_id,
                "resource_type": "NATGateway",
                "region": region,
                "utilization": utilization,
                "status": status,
                "reason": reason,
            })

    except Exception as e:
        print(f"    ⚠️  Skipping NAT Gateways in {region}: {e}")

    return results


def scan_nat_gateways(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans NAT Gateways in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning NAT Gateways across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} NAT Gateways found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ NAT Gateway scan complete: {len(all_results)} NAT Gateways "
          f"({zombie_total} zombies).")
    return all_results
