"""
zombie_detector.py
==================
Orchestration module — runs all three scanners, classifies results,
saves them to the SQLite database, and prints a summary report.

This is the brain of the Ghost Resource Exterminator.
Run directly, or imported by the scheduler and Streamlit dashboard.
"""

from __future__ import annotations
import sys
import io

# ── Force UTF-8 stdout/stderr on Windows (fixes charmap codec errors) ─────────
# Wrapper removed to prevent crashes

from scanner import (
    scan_ec2_instances,
    scan_ebs_volumes,
    scan_snapshots,
    scan_eips,
    scan_elbs,
    scan_security_groups,
    scan_amis,
    scan_stopped_ec2,
    scan_efs,
    scan_nat_gateways,
)  # type: ignore[import-not-found]
from db import init_db, save_resource, clear_resources  # type: ignore[import-not-found]
from config import validate_config  # type: ignore[import-not-found]
from typing import Optional, List, Dict

# ── ANSI colour codes for terminal output ────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _print_banner() -> None:
    """Prints the Ghost Resource Exterminator ASCII banner."""
    banner = f"""
{RED}{BOLD}
 ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝
██║  ███╗███████║██║   ██║███████╗   ██║
██║   ██║██╔══██║██║   ██║╚════██║   ██║
╚██████╔╝██║  ██║╚██████╔╝███████║   ██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝
{CYAN}  R E S O U R C E   E X T E R M I N A T O R
{RESET}"""
    print(banner)


def scan_all(
    clear_before_scan: bool = True,
    regions: Optional[List[str]] = None,
    resource_types: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Main entry point for zombie detection.

    Args:
        clear_before_scan: Wipe old records before inserting new ones.
        regions: Optional list of specific regions to scan, e.g. ['us-east-1', 'ap-south-1'].
                 If None, scans ALL active AWS regions automatically.
        resource_types: Optional list of specific resource types to scan, e.g. ['EC2', 'SecurityGroup'].
                        If None, scans all resource types.

    Returns:
        Combined list of all scanned resources.
    """
    _print_banner()

    # Step 1: Validate configuration
    if not validate_config():
        print(f"{RED}❌ Configuration invalid. Please check your .env file.{RESET}")
        return []

    # Show scan scope
    if regions:
        print(f"{CYAN}📍 Single-region mode: scanning {', '.join(regions)}{RESET}")
    else:
        print(f"{CYAN}🌍 Multi-region mode: scanning all active AWS regions{RESET}")

    if resource_types:
        print(f"{CYAN}🔍 Resource type filter: {', '.join(resource_types)}{RESET}")
    else:
        print(f"{CYAN}🔍 Resource type filter: ALL{RESET}")

    # Step 2: Initialise SQLite database
    init_db()

    # Step 3: Clear old data for a fresh scan
    if clear_before_scan:
        clear_resources(resource_types=resource_types)

    all_resources = []

    # Map of resource types to scanner functions
    scanners = {
        "EC2": scan_ec2_instances,
        "EBS": scan_ebs_volumes,
        "Snapshot": scan_snapshots,
        "EIP": scan_eips,
        "ELB": scan_elbs,
        "SecurityGroup": scan_security_groups,
        "AMI": scan_amis,
        "StoppedEC2": scan_stopped_ec2,
        "EFS": scan_efs,
        "NATGateway": scan_nat_gateways,
    }

    # Step 4: Run each scanner if it matches the filter
    for rtype, scanner_fn in scanners.items():
        if not resource_types or rtype in resource_types:
            try:
                all_resources.extend(scanner_fn(regions=regions))
            except Exception as e:
                print(f"{RED}❌ Scanner error for {rtype}: {e}{RESET}")

    # Step 5: Save each resource to the database

    print(f"\n{CYAN}💾 Saving {len(all_resources)} resources to database...{RESET}")
    for resource in all_resources:
        save_resource(
            resource_id=resource["resource_id"],
            resource_type=resource["resource_type"],
            region=resource["region"],
            utilization=resource["utilization"],
            status=resource["status"],
            reason=resource["reason"],
        )

    # Step 6: Print summary report
    _print_summary(all_resources)

    return all_resources


def _print_summary(resources: list[dict]) -> None:
    """Prints a formatted summary table of scan results to the terminal."""
    zombies = [r for r in resources if r["status"] == "Zombie"]
    active  = [r for r in resources if r["status"] == "Active"]

    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  📊 SCAN SUMMARY REPORT{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"  Total resources scanned : {len(resources)}")
    print(f"  {RED}🎯 Zombie resources     : {len(zombies)}{RESET}")
    print(f"  {GREEN}✅ Active resources     : {len(active)}{RESET}")

    if zombies:
        print(f"\n{BOLD}  Zombie Resources Found:{RESET}")
        print(f"  {'─' * 56}")
        print(f"  {'Type':<12} {'Resource ID':<25} {'Status':<8} Reason")
        print(f"  {'─' * 56}")
        for z in zombies:
            short_reason = z["reason"][:45] + "..." if len(z["reason"]) > 45 else z["reason"]
            print(f"  {z['resource_type']:<12} {z['resource_id']:<25} {RED}{z['status']:<8}{RESET} {short_reason}")

    print(f"\n{GREEN}✅ Results saved to database. Launch dashboard to view full report.{RESET}")
    print(f"   Run: {CYAN}streamlit run dashboard/app.py{RESET}\n")
