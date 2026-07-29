"""
s3_uploader.py
==============
Helper module for Ghost Resource Exterminator.

Uploads zombie-resource CSV/JSON reports to S3, organized by AWS Account ID
so each user's reports are isolated under their own prefix:

    s3://chittesh-demo/reports/<account_id>/<timestamp>_zombie_resources_report.csv

The S3 client is built using the same credential resolution logic as the rest
of the app (session_state → .env → default boto3 chain), so no extra config
is needed.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd  # type: ignore

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
S3_BUCKET = "chittesh-demo"
S3_PREFIX = "reports"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_s3_client(region: Optional[str] = None):
    """
    Creates a boto3 S3 client using the credential resolution order:
      1. Streamlit session_state (login-page credentials)
      2. .env / environment variables
      3. Default boto3 credential chain (IAM role, ~/.aws/credentials, etc.)

    Args:
        region: Optional region override for the S3 client.

    Returns:
        A boto3 S3 client.
    """
    import boto3  # type: ignore
    from config import get_boto3_kwargs  # type: ignore

    kwargs = get_boto3_kwargs(region=region)
    session = boto3.Session(**kwargs)
    return session.client("s3")


def _resolve_account_id() -> str:
    """
    Returns the AWS Account ID from Streamlit session_state (parsed from the
    identity ARN stored at login) or falls back to 'unknown'.

    The identity string is stored as:
        "Account: <account_id> | arn:aws:iam::<account_id>:..."
    """
    account_id = "unknown"
    try:
        import streamlit as st  # type: ignore

        identity: str = st.session_state.get("aws_identity", "")
        # Format: "Account: 123456789012 | arn:aws:..."
        if identity and "Account:" in identity:
            part = identity.split("Account:")[1].strip()
            account_id = part.split("|")[0].strip()
        elif identity and "arn:aws" in identity:
            # Fallback: extract account from ARN
            arn_parts = identity.split(":")
            if len(arn_parts) >= 5:
                account_id = arn_parts[4]
    except Exception:
        pass
    return account_id


def _build_s3_key(account_id: str, file_ext: str = "csv") -> str:
    """
    Generates a timestamped, account-scoped S3 key.

    Pattern: reports/<account_id>/<YYYY-MM-DD_HH-MM-SS>_zombie_resources_report.<ext>

    Args:
        account_id: AWS Account ID string.
        file_ext: File extension without the dot ('csv' or 'json').

    Returns:
        Full S3 key string.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{ts}_zombie_resources_report.{file_ext}"
    return f"{S3_PREFIX}/{account_id}/{filename}"


# ── Public API ────────────────────────────────────────────────────────────────

def upload_report_to_s3(
    df: pd.DataFrame,
    bucket: str = S3_BUCKET,
    account_id: Optional[str] = None,
    region: Optional[str] = None,
    file_format: str = "csv",
) -> tuple[bool, str]:
    """
    Uploads a pandas DataFrame as a CSV (or JSON) report to S3.

    The report is stored at:
        s3://<bucket>/reports/<account_id>/<timestamp>_zombie_resources_report.<ext>

    Args:
        df:          The DataFrame to upload.
        bucket:      Target S3 bucket name (default: 'chittesh-demo').
        account_id:  AWS Account ID to use as folder prefix. If None, auto-resolved
                     from Streamlit session_state.
        region:      AWS region for the S3 client. If None, uses session or env default.
        file_format: 'csv' or 'json'.

    Returns:
        (success: bool, message: str)
        On success, message is the S3 URI (s3://bucket/key).
        On failure, message is a human-readable error description.
    """
    if df is None or df.empty:
        return False, "No data to upload — run a scan first."

    # Resolve account id
    resolved_account = account_id or _resolve_account_id()

    # Build content bytes
    try:
        if file_format == "json":
            df_copy = df.copy()
            if "detected_at" in df_copy.columns:
                df_copy["detected_at"] = df_copy["detected_at"].astype(str)
            body_bytes = df_copy.to_json(orient="records", indent=2).encode("utf-8")
            content_type = "application/json"
            ext = "json"
        else:
            body_bytes = df.to_csv(index=False).encode("utf-8")
            content_type = "text/csv"
            ext = "csv"
    except Exception as exc:
        msg = f"Failed to serialize report data: {exc}"
        logger.error(msg)
        return False, msg

    # Build S3 key
    s3_key = _build_s3_key(resolved_account, ext)
    s3_uri = f"s3://{bucket}/{s3_key}"

    # Upload
    try:
        client = _build_s3_client(region=region)
        client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=body_bytes,
            ContentType=content_type,
            Metadata={
                "account-id": resolved_account,
                "uploaded-by": "ghost-resource-exterminator",
            },
        )
        logger.info("Uploaded report to %s", s3_uri)
        return True, s3_uri

    except Exception as exc:
        import botocore.exceptions  # type: ignore

        if isinstance(exc, botocore.exceptions.ClientError):
            code = exc.response["Error"]["Code"]
            msg_detail = exc.response["Error"]["Message"]
            if code == "NoSuchBucket":
                msg = f"Bucket '{bucket}' does not exist or is not accessible."
            elif code in ("AccessDenied", "Forbidden"):
                msg = f"Access denied — ensure your IAM user has s3:PutObject on '{bucket}'."
            else:
                msg = f"AWS S3 error ({code}): {msg_detail}"
        elif isinstance(exc, botocore.exceptions.NoCredentialsError):
            msg = "No AWS credentials available. Please log in first."
        else:
            msg = f"Upload failed: {exc}"

        logger.error(msg)
        return False, msg


def upload_report_bundle_to_s3(
    bundle: dict,
    bucket: str = S3_BUCKET,
    account_id: Optional[str] = None,
    region: Optional[str] = None,
) -> tuple[bool, dict]:
    """
    Uploads a full report bundle (HTML + CSV) to S3 under a shared timestamped prefix.

    The bundle dict is produced by report_generator.generate_report_bundle() and
    must contain keys: 'html' (bytes), 'csv' (bytes), 'filename_prefix' (str).

    Uploaded paths:
        reports/<account_id>/<filename_prefix>/zombie_report.html
        reports/<account_id>/<filename_prefix>/zombie_report.csv

    Args:
        bundle:     Output of generate_report_bundle().
        bucket:     Target S3 bucket (default: 'chittesh-demo').
        account_id: AWS Account ID prefix. Auto-resolved if None.
        region:     AWS region for the S3 client. If None, uses session/env default.

    Returns:
        (success: bool, result: dict)
        On success: result = {"html_uri": str, "csv_uri": str}
        On failure: result = {"error": str}
    """
    resolved_account = account_id or _resolve_account_id()
    prefix = bundle.get("filename_prefix", datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S"))
    folder = f"{S3_PREFIX}/{resolved_account}/{prefix}"

    uploads = [
        (f"{folder}/zombie_report.html", bundle.get("html", b""), "text/html"),
        (f"{folder}/zombie_report.csv",  bundle.get("csv",  b""), "text/csv"),
    ]

    try:
        client = _build_s3_client(region=region)
        uris: dict[str, str] = {}

        for key, body, content_type in uploads:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={
                    "account-id": resolved_account,
                    "uploaded-by": "ghost-resource-exterminator",
                },
            )
            ext = key.rsplit(".", 1)[-1]
            uris[f"{ext}_uri"] = f"s3://{bucket}/{key}"
            logger.info("Uploaded %s to s3://%s/%s", ext.upper(), bucket, key)

        return True, uris

    except Exception as exc:
        import botocore.exceptions  # type: ignore

        if isinstance(exc, botocore.exceptions.ClientError):
            code = exc.response["Error"]["Code"]
            msg_detail = exc.response["Error"]["Message"]
            if code == "NoSuchBucket":
                msg = f"Bucket '{bucket}' does not exist or is not accessible."
            elif code in ("AccessDenied", "Forbidden"):
                msg = f"Access denied — ensure your IAM user has s3:PutObject on '{bucket}'."
            else:
                msg = f"AWS S3 error ({code}): {msg_detail}"
        elif isinstance(exc, botocore.exceptions.NoCredentialsError):
            msg = "No AWS credentials available. Please log in first."
        else:
            msg = f"Bundle upload failed: {exc}"

        logger.error(msg)
        return False, {"error": msg}


# ══════════════════════════════════════════════════════════════════════════════
# SCAN HISTORY
# ══════════════════════════════════════════════════════════════════════════════
#
# Every scan is stored as a versioned snapshot under:
#   s3://chittesh-demo/history/<account_id>/<YYYY-MM-DD_HH-MM-SS>/
#       scan_meta.json      ← lightweight summary (timestamp, region, counts …)
#       scan_results.json   ← full resource list
#
# This lets users browse all past scans and replay any of them in the dashboard.

_HISTORY_PREFIX = "history"


def save_scan_history_to_s3(
    resources: list,
    account_id: Optional[str] = None,
    region: str = "multi-region",
    scan_types: Optional[list] = None,
    bucket: str = S3_BUCKET,
    s3_region: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Persists a completed scan as a versioned history snapshot in S3.

    Writes two objects under  history/<account_id>/<timestamp>/:
      - scan_meta.json    — lightweight header (timestamp, region, summary counts)
      - scan_results.json — full array of scanned resource dicts

    Args:
        resources:   The list returned by scan_all().
        account_id:  AWS Account ID. Auto-resolved from session_state if None.
        region:      Human-readable region label for the metadata.
        scan_types:  List of resource types that were scanned.
        bucket:      Target bucket (default 'chittesh-demo').
        s3_region:   Region for the boto3 S3 client.

    Returns:
        (success: bool, folder_uri: str | error_message: str)
    """
    import json

    resolved_account = account_id or _resolve_account_id()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    folder = f"{_HISTORY_PREFIX}/{resolved_account}/{ts}"

    zombies = [r for r in resources if r.get("status") == "Zombie"]
    active  = [r for r in resources if r.get("status") == "Active"]

    meta = {
        "timestamp":   ts,
        "account_id":  resolved_account,
        "region":      region,
        "scan_types":  scan_types or [],
        "total":       len(resources),
        "zombie":      len(zombies),
        "active":      len(active),
        "saved_at":    datetime.now(timezone.utc).isoformat(),
    }

    # Serialise resources — convert any non-serialisable types to str
    def _safe(obj):
        try:
            return str(obj)
        except Exception:
            return ""

    try:
        client = _build_s3_client(region=s3_region)

        # Upload meta
        client.put_object(
            Bucket=bucket,
            Key=f"{folder}/scan_meta.json",
            Body=json.dumps(meta, indent=2, default=_safe).encode("utf-8"),
            ContentType="application/json",
            Metadata={"account-id": resolved_account, "uploaded-by": "ghost-resource-exterminator"},
        )

        # Upload full results
        client.put_object(
            Bucket=bucket,
            Key=f"{folder}/scan_results.json",
            Body=json.dumps(resources, indent=2, default=_safe).encode("utf-8"),
            ContentType="application/json",
            Metadata={"account-id": resolved_account, "uploaded-by": "ghost-resource-exterminator"},
        )

        uri = f"s3://{bucket}/{folder}/"
        logger.info("Scan history saved to %s", uri)
        return True, uri

    except Exception as exc:
        import botocore.exceptions  # type: ignore

        if isinstance(exc, botocore.exceptions.ClientError):
            code = exc.response["Error"]["Code"]
            if code == "NoSuchBucket":
                msg = f"Bucket '{bucket}' not found."
            elif code in ("AccessDenied", "Forbidden"):
                msg = f"Access denied — s3:PutObject required on '{bucket}'."
            else:
                msg = f"AWS error ({code}): {exc.response['Error']['Message']}"
        elif isinstance(exc, botocore.exceptions.NoCredentialsError):
            msg = "No credentials available."
        else:
            msg = str(exc)

        logger.warning("Could not save scan history: %s", msg)
        return False, msg


def list_scan_history(
    account_id: Optional[str] = None,
    bucket: str = S3_BUCKET,
    s3_region: Optional[str] = None,
    max_entries: int = 50,
) -> tuple[bool, list]:
    """
    Lists all historical scan snapshots for a user, newest-first.

    Args:
        account_id:  AWS Account ID. Auto-resolved from session_state if None.
        bucket:      Source bucket (default 'chittesh-demo').
        s3_region:   Region for the boto3 S3 client.
        max_entries: Maximum number of history entries to return.

    Returns:
        (success: bool, entries: list[dict])
        Each entry dict has keys from scan_meta.json plus 'folder_prefix'.
        On failure returns (False, []).
    """
    import json

    resolved_account = account_id or _resolve_account_id()
    prefix = f"{_HISTORY_PREFIX}/{resolved_account}/"

    try:
        client = _build_s3_client(region=s3_region)

        # List all scan_meta.json objects under the user's history prefix
        paginator = client.get_paginator("list_objects_v2")
        meta_keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/scan_meta.json"):
                    meta_keys.append(key)

        # Sort newest-first by key name (timestamps in the path are lexicographically sortable)
        meta_keys.sort(reverse=True)
        meta_keys = meta_keys[:max_entries]

        entries = []
        for key in meta_keys:
            try:
                resp = client.get_object(Bucket=bucket, Key=key)
                meta = json.loads(resp["Body"].read().decode("utf-8"))
                # folder_prefix = e.g. "history/<account>/<timestamp>"
                meta["folder_prefix"] = key.replace("/scan_meta.json", "")
                entries.append(meta)
            except Exception:
                continue

        return True, entries

    except Exception as exc:
        logger.warning("Could not list scan history: %s", exc)
        return False, []


def load_scan_history_entry(
    folder_prefix: str,
    bucket: str = S3_BUCKET,
    s3_region: Optional[str] = None,
) -> tuple[bool, list]:
    """
    Loads the full resource list for a specific historical scan.

    Args:
        folder_prefix: The S3 key prefix (e.g. 'history/<account>/<timestamp>').
        bucket:        Source bucket (default 'chittesh-demo').
        s3_region:     Region for the boto3 S3 client.

    Returns:
        (success: bool, resources: list[dict])
        On failure returns (False, []).
    """
    import json

    key = f"{folder_prefix}/scan_results.json"
    try:
        client = _build_s3_client(region=s3_region)
        resp = client.get_object(Bucket=bucket, Key=key)
        resources = json.loads(resp["Body"].read().decode("utf-8"))
        return True, resources
    except Exception as exc:
        logger.warning("Could not load history entry '%s': %s", folder_prefix, exc)
        return False, []


def delete_scan_history_entry(
    folder_prefix: str,
    bucket: str = S3_BUCKET,
    s3_region: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Deletes both objects (scan_meta.json + scan_results.json) for a history entry.

    Args:
        folder_prefix: The S3 key prefix (e.g. 'history/<account>/<timestamp>').
        bucket:        Target bucket.
        s3_region:     Region for the boto3 S3 client.

    Returns:
        (success: bool, message: str)
    """
    keys_to_delete = [
        {"Key": f"{folder_prefix}/scan_meta.json"},
        {"Key": f"{folder_prefix}/scan_results.json"},
    ]
    try:
        client = _build_s3_client(region=s3_region)
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": keys_to_delete, "Quiet": True},
        )
        logger.info("Deleted history entry: %s", folder_prefix)
        return True, f"Deleted `s3://{bucket}/{folder_prefix}/`"
    except Exception as exc:
        msg = str(exc)
        logger.warning("Could not delete history entry: %s", msg)
        return False, msg
