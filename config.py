"""
config.py
=========
Centralized configuration module for Ghost Resource Exterminator.

Loads AWS credentials and detection thresholds from environment variables
(.env file). All other modules import from here — no credentials are
ever hard-coded in the codebase (security best practice).

Multi-region support: get_all_regions() discovers every enabled AWS region
automatically so scanners cover the entire account.
"""

import utf8_fix  # noqa: F401 — forces UTF-8 stdout/stderr on Windows
import os
from typing import Optional
from dotenv import load_dotenv  # type: ignore

# Load variables from .env file into the environment
load_dotenv()


# ── AWS Credentials & Region ─────────────────────────────────────────────────
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")  # for temporary credentials

# ── Zombie Detection Thresholds ───────────────────────────────────────────────
# EC2: Average CPU utilization below this % → Zombie
EC2_CPU_ZOMBIE_THRESHOLD = float(os.getenv("EC2_CPU_ZOMBIE_THRESHOLD", "1.0"))

# Snapshot: Older than this many days → Zombie
SNAPSHOT_AGE_DAYS = int(os.getenv("SNAPSHOT_AGE_DAYS", "30"))

# CloudWatch: How many days back to look for metrics
CLOUDWATCH_DAYS = int(os.getenv("CLOUDWATCH_DAYS", "7"))

# ── Database Path ─────────────────────────────────────────────────────────────
# SQLite database stored locally in the data/ folder
import pathlib
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = str(BASE_DIR / "data" / "zombie_resources.db")

# ── Boto3 Session Arguments ───────────────────────────────────────────────────
def get_boto3_kwargs(region: Optional[str] = None) -> dict:
    """
    Returns keyword arguments dict for boto3.Session().

    Priority order for credentials:
      1. Streamlit session_state (entered via login page) — preferred
      2. .env / environment variables
      3. boto3 default credential chain (~/.aws/credentials, IAM role, etc.)

    Args:
        region: Override region. If None, uses session_state or AWS_DEFAULT_REGION.
    """
    ss_key = ss_secret = ss_region = ss_token = None
    # Try to pull from Streamlit session_state (login page credentials)
    try:
        import streamlit as st  # type: ignore
        ss = st.session_state
        ss_key    = ss.get("aws_access_key_id")
        ss_secret = ss.get("aws_secret_access_key")
        ss_region = ss.get("aws_default_region")
        ss_token  = ss.get("aws_session_token")
    except Exception:
        pass

    # Resolve final values, falling back to env vars if session_state is empty
    resolved_region = region or ss_region or AWS_DEFAULT_REGION
    resolved_key    = ss_key    or AWS_ACCESS_KEY_ID
    resolved_secret = ss_secret or AWS_SECRET_ACCESS_KEY
    resolved_token  = ss_token  or AWS_SESSION_TOKEN

    kwargs: dict = {"region_name": resolved_region}
    
    # Only append credentials if they exist; otherwise let boto3 use the default chain (IAM role)
    if resolved_key and resolved_secret:
        kwargs["aws_access_key_id"]     = resolved_key
        kwargs["aws_secret_access_key"] = resolved_secret
    if resolved_token:
        kwargs["aws_session_token"] = resolved_token
        
    return kwargs


def get_all_regions() -> list:
    """
    Discovers all currently enabled/opted-in AWS regions for this account
    by calling EC2 DescribeRegions from the default region.

    Returns:
        Sorted list of region name strings, e.g. ['ap-south-1', 'eu-west-1', ...]
        Falls back to a hardcoded list of common regions if the API call fails.
    """
    import boto3  # type: ignore

    # Common fallback regions if DescribeRegions fails
    FALLBACK_REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "ap-south-1", "ap-southeast-1", "ap-southeast-2",
        "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
        "ca-central-1",
        "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-north-1",
        "sa-east-1",
    ]

    try:
        session = boto3.Session(**get_boto3_kwargs())
        ec2 = session.client("ec2")
        # "all" includes regions you have opted into
        response = ec2.describe_regions(AllRegions=False)
        regions = sorted(
            r["RegionName"] for r in response["Regions"]
            if r["OptInStatus"] in ("opt-in-not-required", "opted-in")
        )
        print(f"🌍 Discovered {len(regions)} active AWS regions.")
        return regions
    except Exception as e:
        print(f"⚠️  Could not auto-discover regions ({e}). Using fallback list.")
        return FALLBACK_REGIONS


def validate_config() -> bool:
    """
    Validates that minimum required configuration is present.
    Returns True if configuration looks valid, False otherwise.
    """
    if not AWS_DEFAULT_REGION:
        print("❌ ERROR: AWS_DEFAULT_REGION is not set in .env")
        return False

    # If not using env credentials, boto3 will use ~/.aws/credentials
    if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
        print("⚠️  WARNING: AWS keys not in .env. Using default credential chain.")

    print(f"✅ Config valid | Default region: {AWS_DEFAULT_REGION} | Mode: MULTI-REGION")
    return True
