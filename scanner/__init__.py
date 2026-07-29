"""
scanner/__init__.py
===================
Makes the scanner/ directory a Python package.
Exposes the three scanner functions from a single import.
"""

from .ec2_scanner import scan_ec2_instances  # type: ignore[import-not-found]
from .ebs_scanner import scan_ebs_volumes  # type: ignore[import-not-found]
from .snapshot_scanner import scan_snapshots  # type: ignore[import-not-found]
from .eip_scanner import scan_eips  # type: ignore[import-not-found]
from .elb_scanner import scan_elbs  # type: ignore[import-not-found]
from .security_group_scanner import scan_security_groups  # type: ignore[import-not-found]
from .ami_scanner import scan_amis  # type: ignore[import-not-found]
from .stopped_ec2_scanner import scan_stopped_ec2  # type: ignore[import-not-found]
from .efs_scanner import scan_efs  # type: ignore[import-not-found]
from .nat_gateway_scanner import scan_nat_gateways  # type: ignore[import-not-found]

__all__ = [
    "scan_ec2_instances",
    "scan_ebs_volumes",
    "scan_snapshots",
    "scan_eips",
    "scan_elbs",
    "scan_security_groups",
    "scan_amis",
    "scan_stopped_ec2",
    "scan_efs",
    "scan_nat_gateways",
]
