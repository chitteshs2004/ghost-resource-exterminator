"""
scanner/elb_scanner.py
======================
Scans ALL AWS regions for Classic Load Balancers (CLBs) and Application/Network Load Balancers (ALBs/NLBs)
that are idle or have no active targets/traffic.

Zombie Rules:
  - Classic ELB: No registered instances, or 0 traffic over last CLOUDWATCH_DAYS days.
  - ALB/NLB: No target groups, or all target groups have 0 registered targets, or 0 traffic over last CLOUDWATCH_DAYS days.
"""

from __future__ import annotations
import boto3  # type: ignore[import-not-found]
from datetime import datetime, timedelta, timezone
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_boto3_kwargs, get_all_regions, CLOUDWATCH_DAYS  # type: ignore[import-not-found]


def _get_elb_cw_metric(cloudwatch, namespace: str, metric_name: str, dimension_name: str, dimension_value: str, days: int) -> float:
    """
    Queries CloudWatch for the sum of a metric for a load balancer over the specified number of days.
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    try:
        response = cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[{"Name": dimension_name, "Value": dimension_value}],
            StartTime=start_time,
            EndTime=now,
            Period=86400,  # 1-day granularity
            Statistics=["Sum"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return 0.0
        return float(sum(dp["Sum"] for dp in datapoints))
    except Exception as e:
        # Silently fail and return -1.0 so we can fallback to other indicators
        return -1.0


def _scan_region(region: str) -> list[dict]:
    """
    Scans a single AWS region for idle Load Balancers.
    """
    results = []
    try:
        session = boto3.Session(**get_boto3_kwargs(region))
        elb_client = session.client("elb")      # Classic
        elbv2_client = session.client("elbv2")  # ALB/NLB
        cw_client = session.client("cloudwatch")

        # 1. Scan Classic Load Balancers
        try:
            clbs = elb_client.describe_load_balancers()
            for lb in clbs.get("LoadBalancerDescriptions", []):
                name = lb["LoadBalancerName"]
                instances = lb.get("Instances", [])
                num_instances = len(instances)

                # Check CloudWatch RequestCount
                traffic = _get_elb_cw_metric(
                    cw_client,
                    namespace="AWS/ELB",
                    metric_name="RequestCount",
                    dimension_name="LoadBalancerName",
                    dimension_value=name,
                    days=CLOUDWATCH_DAYS
                )

                is_zombie = False
                if num_instances == 0:
                    is_zombie = True
                    reason = "Classic Load Balancer has 0 registered EC2 instances."
                elif traffic == 0.0:
                    is_zombie = True
                    reason = f"Classic Load Balancer has 0 requests over the last {CLOUDWATCH_DAYS} days."
                else:
                    reason = f"Active CLB with {num_instances} instance(s) and active traffic."

                status = "Zombie" if is_zombie else "Active"
                utilization = 0.0 if is_zombie else 100.0
                icon = "🧟" if status == "Zombie" else "✅"
                print(f"    {icon} CLB: {name} | Instances: {num_instances} | Traffic: {traffic} | {status}")

                results.append({
                    "resource_id": name,
                    "resource_type": "ELB",
                    "region": region,
                    "utilization": utilization,
                    "status": status,
                    "reason": reason,
                })
        except Exception as clb_err:
            print(f"    ⚠️  Classic ELB skip in {region}: {clb_err}")

        # 2. Scan Application / Network Load Balancers
        try:
            elbv2s = elbv2_client.describe_load_balancers()
            for lb in elbv2s.get("LoadBalancers", []):
                name = lb["LoadBalancerName"]
                arn = lb["LoadBalancerArn"]
                lb_type = lb.get("Type", "application")

                # Extract load balancer suffix for CloudWatch dimensions
                # e.g., app/my-load-balancer/50dc6c495c0c9188
                lb_suffix = ""
                if "/" in arn:
                    lb_suffix = "/".join(arn.split("/")[-3:])

                # Get Target Groups
                tgs = elbv2_client.describe_target_groups(LoadBalancerArn=arn)
                total_targets = 0
                has_target_groups = len(tgs.get("TargetGroups", [])) > 0

                if has_target_groups:
                    for tg in tgs["TargetGroups"]:
                        tg_arn = tg["TargetGroupArn"]
                        try:
                            health_resp = elbv2_client.describe_target_health(TargetGroupArn=tg_arn)
                            total_targets += len(health_resp.get("TargetHealthDescriptions", []))
                        except Exception:
                            pass

                # Query CloudWatch based on type
                traffic = -1.0
                if lb_suffix:
                    if lb_type == "application":
                        traffic = _get_elb_cw_metric(
                            cw_client,
                            namespace="AWS/ApplicationELB",
                            metric_name="RequestCount",
                            dimension_name="LoadBalancer",
                            dimension_value=lb_suffix,
                            days=CLOUDWATCH_DAYS
                        )
                    elif lb_type == "network":
                        traffic = _get_elb_cw_metric(
                            cw_client,
                            namespace="AWS/NetworkELB",
                            metric_name="ActiveConnectionCount",
                            dimension_name="LoadBalancer",
                            dimension_value=lb_suffix,
                            days=CLOUDWATCH_DAYS
                        )

                is_zombie = False
                if not has_target_groups:
                    is_zombie = True
                    reason = f"{lb_type.upper()} has no registered target groups."
                elif total_targets == 0:
                    is_zombie = True
                    reason = f"{lb_type.upper()} has 0 registered targets in target groups."
                elif traffic == 0.0:
                    is_zombie = True
                    reason = f"{lb_type.upper()} has 0 requests/connections over the last {CLOUDWATCH_DAYS} days."
                else:
                    reason = f"Active {lb_type.upper()} with {total_targets} target(s) and active traffic."

                status = "Zombie" if is_zombie else "Active"
                utilization = 0.0 if is_zombie else 100.0
                icon = "🧟" if status == "Zombie" else "✅"
                print(f"    {icon} {lb_type.upper()}: {name} | Targets: {total_targets} | Traffic: {traffic} | {status}")

                results.append({
                    "resource_id": arn,
                    "resource_type": "ELB",
                    "region": region,
                    "utilization": utilization,
                    "status": status,
                    "reason": reason,
                })
        except Exception as elbv2_err:
            print(f"    ⚠️  ELBv2 skip in {region}: {elbv2_err}")

    except Exception as e:
        print(f"    ⚠️  Skipping Load Balancers in {region}: {e}")

    return results


def scan_elbs(regions: Optional[list] = None) -> list[dict]:
    """
    Iterates over AWS regions and scans Load Balancers in each.
    """
    target_regions = regions if regions else get_all_regions()
    all_results = []

    print(f"\n🔍 Scanning Load Balancers across {len(target_regions)} region(s)...")

    for region in target_regions:
        print(f"  📍 Region: {region}")
        region_results = _scan_region(region)
        all_results.extend(region_results)
        if region_results:
            zombies = sum(1 for r in region_results if r["status"] == "Zombie")
            print(f"     → {len(region_results)} load balancers found, {zombies} zombies.")

    zombie_total = sum(1 for r in all_results if r["status"] == "Zombie")
    print(f"\n  ✅ ELB scan complete: {len(all_results)} load balancers "
          f"({zombie_total} zombies).")
    return all_results
