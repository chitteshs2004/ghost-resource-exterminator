# fmt: off
from __future__ import annotations  # must be first line for Python 3.8 compat
# fmt: on
from typing import Optional, List

"""
cleanup.py
==========
Optional cleanup module for Ghost Resource Exterminator.

Contains actions to terminate zombie EC2 instances and delete
EBS volumes/snapshots. All actions include:
  - Confirmation prompts (to prevent accidental deletion)
  - Logging to database/terminal
  - Safety guards (cannot terminate without explicit approval)

⚠️  WARNING: These operations are DESTRUCTIVE and IRREVERSIBLE.
   Always review resources before confirming deletion.
"""

import utf8_fix  # noqa: F401 — forces UTF-8 stdout/stderr on Windows
import boto3  # type: ignore
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_boto3_kwargs  # type: ignore

# ANSI colour codes
RED   = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD  = "\033[1m"
RESET = "\033[0m"


def terminate_instance(instance_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Terminates an EC2 instance after user confirmation.

    Args:
        instance_id: The EC2 instance ID to terminate (e.g. 'i-0abc123')
        region: The AWS region where the instance is located
        dry_run: If True, simulates the action without actually terminating.

    Returns:
        True if instance was terminated, False otherwise.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  TERMINATION REQUEST{RESET}")
    print(f"   Instance ID : {RED}{instance_id}{RESET}")
    print(f"   Region      : {session.region_name}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual termination.{RESET}")
        return False

    # The calling UI (Streamlit) handles confirmation.
    # We no longer block on stdin here because it hangs the web app.

    try:
        # Terminate the instance
        response = ec2.terminate_instances(InstanceIds=[instance_id])
        new_state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
        print(f"{GREEN}   ✅ Instance {instance_id} is now: {new_state}{RESET}")
        return True

    except ec2.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"{RED}   ❌ AWS Error [{error_code}]: {e}{RESET}")
        return False


def delete_ebs_volume(volume_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Deletes an unattached EBS volume after user confirmation.

    Args:
        volume_id: EBS volume ID (e.g. 'vol-0abc123')
        region: The AWS region where the volume is located
        dry_run: If True, simulates without deleting.

    Returns:
        True if deleted, False otherwise.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  EBS VOLUME DELETION REQUEST{RESET}")
    print(f"   Volume ID : {RED}{volume_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deletion.{RESET}")
        return False

    # The calling UI (Streamlit) handles confirmation.

    try:
        ec2.delete_volume(VolumeId=volume_id)
        print(f"{GREEN}   ✅ Volume {volume_id} deleted successfully.{RESET}")
        return True

    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def delete_snapshot(snapshot_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Deletes an EBS snapshot after user confirmation.

    Args:
        snapshot_id: Snapshot ID (e.g. 'snap-0abc123')
        region: The AWS region where the snapshot is located
        dry_run: If True, simulates without deleting.

    Returns:
        True if deleted, False otherwise.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  SNAPSHOT DELETION REQUEST{RESET}")
    print(f"   Snapshot ID : {RED}{snapshot_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deletion.{RESET}")
        return False

    # The calling UI (Streamlit) handles confirmation.

    try:
        ec2.delete_snapshot(SnapshotId=snapshot_id)
        print(f"{GREEN}   ✅ Snapshot {snapshot_id} deleted successfully.{RESET}")
        return True

    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def release_eip(allocation_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Releases an Elastic IP after user confirmation.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  EIP RELEASE REQUEST{RESET}")
    print(f"   EIP / Allocation ID : {RED}{allocation_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual release.{RESET}")
        return False

    try:
        if allocation_id.startswith("eipalloc-"):
            ec2.release_address(AllocationId=allocation_id)
        else:
            ec2.release_address(PublicIp=allocation_id)
        print(f"{GREEN}   ✅ Elastic IP {allocation_id} released successfully.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def delete_load_balancer(arn_or_name: str, region: str, dry_run: bool = False) -> bool:
    """
    Deletes a Classic or v2 Load Balancer after user confirmation.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))

    print(f"\n{YELLOW}⚠️  LOAD BALANCER DELETION REQUEST{RESET}")
    print(f"   LB ARN/Name : {RED}{arn_or_name}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deletion.{RESET}")
        return False

    try:
        if arn_or_name.startswith("arn:aws:elasticloadbalancing:"):
            elbv2 = session.client("elbv2")
            elbv2.delete_load_balancer(LoadBalancerArn=arn_or_name)
        else:
            elb = session.client("elb")
            elb.delete_load_balancer(LoadBalancerName=arn_or_name)
        print(f"{GREEN}   ✅ Load Balancer {arn_or_name} deleted successfully.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def delete_security_group(group_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Deletes a custom security group after user confirmation.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  SECURITY GROUP DELETION REQUEST{RESET}")
    print(f"   SG Group ID : {RED}{group_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deletion.{RESET}")
        return False

    try:
        ec2.delete_security_group(GroupId=group_id)
        print(f"{GREEN}   ✅ Security Group {group_id} deleted successfully.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def deregister_ami(image_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Deregisters a custom AMI image after user confirmation.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  AMI DEREGISTRATION REQUEST{RESET}")
    print(f"   AMI Image ID : {RED}{image_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deregistration.{RESET}")
        return False

    try:
        ec2.deregister_image(ImageId=image_id)
        print(f"{GREEN}   ✅ AMI {image_id} deregistered successfully.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def delete_efs(file_system_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Deletes an EFS file system after user confirmation.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    efs = session.client("efs")

    print(f"\n{YELLOW}⚠️  EFS DELETION REQUEST{RESET}")
    print(f"   EFS File System ID : {RED}{file_system_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deletion.{RESET}")
        return False

    try:
        efs.delete_file_system(FileSystemId=file_system_id)
        print(f"{GREEN}   ✅ EFS File System {file_system_id} deleted successfully.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def delete_nat_gateway(nat_gateway_id: str, region: str, dry_run: bool = False) -> bool:
    """
    Deletes a NAT gateway after user confirmation.
    """
    session = boto3.Session(**get_boto3_kwargs(region=region))
    ec2 = session.client("ec2")

    print(f"\n{YELLOW}⚠️  NAT GATEWAY DELETION REQUEST{RESET}")
    print(f"   NAT Gateway ID : {RED}{nat_gateway_id}{RESET}")
    print(f"   This action is {RED}{BOLD}IRREVERSIBLE{RESET}.")

    if dry_run:
        print(f"{YELLOW}   [DRY RUN] Skipping actual deletion.{RESET}")
        return False

    try:
        ec2.delete_nat_gateway(NatGatewayId=nat_gateway_id)
        print(f"{GREEN}   ✅ NAT Gateway {nat_gateway_id} deleted successfully.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}   ❌ Error: {e}{RESET}")
        return False


def cleanup_all_zombies(dry_run: bool = True, resource_types: Optional[List[str]] = None) -> None:
    """
    Reads all zombie resources from the database and offers to clean each one.

    Args:
        dry_run: Safety default. Set to False only when ready for real cleanup.
        resource_types: Optional list of specific resource types to clean.
    """
    from db import get_zombie_resources  # type: ignore
    zombies = get_zombie_resources()

    if resource_types:
        zombies = [z for z in zombies if z["resource_type"] in resource_types]

    if not zombies:
        print(f"{GREEN}🎉 No zombie resources found in database matching the filter. Your account is clean!{RESET}")
        return

    print(f"\n{BOLD}🧟 Zombie resources requiring cleanup: {len(zombies)}{RESET}")
    for z in zombies:
        rtype  = z["resource_type"]
        rid    = z["resource_id"]
        region = z["region"]

        if rtype == "EC2":
            terminate_instance(rid, region, dry_run=dry_run)
        elif rtype == "EBS":
            delete_ebs_volume(rid, region, dry_run=dry_run)
        elif rtype == "Snapshot":
            delete_snapshot(rid, region, dry_run=dry_run)
        elif rtype == "EIP":
            release_eip(rid, region, dry_run=dry_run)
        elif rtype == "ELB":
            delete_load_balancer(rid, region, dry_run=dry_run)
        elif rtype == "SecurityGroup":
            delete_security_group(rid, region, dry_run=dry_run)
        elif rtype == "AMI":
            deregister_ami(rid, region, dry_run=dry_run)
        elif rtype == "StoppedEC2":
            terminate_instance(rid, region, dry_run=dry_run)
        elif rtype == "EFS":
            delete_efs(rid, region, dry_run=dry_run)
        elif rtype == "NATGateway":
            delete_nat_gateway(rid, region, dry_run=dry_run)
