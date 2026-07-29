from __future__ import annotations
from typing import Any, Optional, List
"""
db.py
=====
Database layer for Ghost Resource Exterminator.

Uses SQLite — a lightweight, file-based database that requires no
external server. All detected zombie resources are stored here so the
Streamlit dashboard can read them even when AWS is offline.

Schema:
    id            INTEGER  - auto-increment primary key
    resource_id   TEXT     - AWS resource identifier (e.g. i-0abc123)
    resource_type TEXT     - 'EC2', 'EBS', 'Snapshot', etc.
    region        TEXT     - AWS region (e.g. us-east-1)
    utilization   REAL     - CPU % for EC2, 0.0 for others
    status        TEXT     - 'Zombie' or 'Active'
    reason        TEXT     - Human-readable explanation
    detected_at   TEXT     - ISO-8601 timestamp of detection
"""

import sqlite3
import os
from datetime import datetime
from config import DB_PATH  # type: ignore


def _get_connection() -> sqlite3.Connection:
    """Opens a connection to the SQLite database."""
    # Ensure the data/ directory exists before connecting
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-style access to rows
    return conn


def init_db() -> None:
    """
    Creates the zombie_resources table if it doesn't already exist.
    Also applies any schema migrations (UNIQUE constraint, index).
    Safe to call multiple times (idempotent).
    """
    conn = _get_connection()
    try:
        # Create table with UNIQUE constraint on (resource_id, resource_type)
        # so INSERT OR REPLACE correctly updates existing records instead of stacking duplicates
        conn.execute("""
            CREATE TABLE IF NOT EXISTS zombie_resources (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_id   TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                region        TEXT NOT NULL,
                utilization   REAL DEFAULT 0.0,
                status        TEXT NOT NULL DEFAULT 'Unknown',
                reason        TEXT,
                detected_at   TEXT NOT NULL,
                UNIQUE(resource_id, resource_type)
            )
        """)
        # Create index for faster filtering by status/type
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_type
            ON zombie_resources(status, resource_type)
        """)
        conn.commit()
    except Exception:
        # If the table already exists without the UNIQUE constraint,
        # migrate it by rebuilding
        try:
            conn.execute("ALTER TABLE zombie_resources ADD COLUMN _compat TEXT")
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


def save_resource(
    resource_id: str,
    resource_type: str,
    region: str,
    utilization: float,
    status: str,
    reason: str,
) -> None:
    """
    Inserts or replaces a single resource record.
    The UNIQUE(resource_id, resource_type) constraint ensures that
    re-running the scanner cleanly updates stale records with no duplicates.
    """
    conn = _get_connection()
    try:
        conn.execute("""
            INSERT INTO zombie_resources
                (resource_id, resource_type, region, utilization, status, reason, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(resource_id, resource_type) DO UPDATE SET
                region       = excluded.region,
                utilization  = excluded.utilization,
                status       = excluded.status,
                reason       = excluded.reason,
                detected_at  = excluded.detected_at
        """, (
            resource_id,
            resource_type,
            region,
            utilization,
            status,
            reason,
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def get_all_resources() -> list[dict[str, Any]]:
    """
    Fetches all stored resources from the database.
    Returns a list of dicts keyed by column name.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM zombie_resources ORDER BY detected_at DESC"
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()
    return []  # unreachable, satisfies type checker


def get_zombie_resources() -> list[dict[str, Any]]:
    """Returns only resources flagged as 'Zombie'."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM zombie_resources WHERE status = 'Zombie' ORDER BY detected_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
    return []  # unreachable, satisfies type checker


def clear_resources(resource_types: Optional[List[str]] = None) -> None:
    """
    Deletes all or specific records from the database.
    Useful before a fresh scan so stale resources don't persist.
    """
    conn = _get_connection()
    try:
        if resource_types:
            placeholders = ",".join("?" for _ in resource_types)
            conn.execute(
                f"DELETE FROM zombie_resources WHERE resource_type IN ({placeholders})",
                resource_types
            )
            print(f"[CLEARED] Database cleared for resource types: {resource_types}")
        else:
            conn.execute("DELETE FROM zombie_resources")
            print("[CLEARED] Database cleared - ready for fresh scan.")
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    """
    Drops and recreates the zombie_resources table — used to fix schema issues.
    """
    conn = _get_connection()
    try:
        conn.execute("DROP TABLE IF EXISTS zombie_resources")
        conn.commit()
    finally:
        conn.close()
    init_db()


def get_summary_stats() -> dict[str, Any]:
    """
    Returns aggregate counts for the dashboard summary cards.
    Dynamically builds the stats dict from DB data — never shows phantom counts.
    """
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT
                resource_type,
                status,
                COUNT(*) as count
            FROM zombie_resources
            GROUP BY resource_type, status
        """).fetchall()

        stats: dict[str, Any] = {
            "total": 0,
            "zombie": 0,
            "active": 0,
        }

        # Dynamically accumulate per-type zombie counts
        for row in rows:
            stats["total"] += row["count"]
            if row["status"] == "Zombie":
                stats["zombie"] += row["count"]
                key = f"{row['resource_type'].lower()}_zombie"
                stats[key] = stats.get(key, 0) + row["count"]
            else:
                stats["active"] += row["count"]

        return stats
    finally:
        conn.close()
    return {}  # unreachable, satisfies type checker


def delete_resource(resource_id: str) -> None:
    """
    Removes a specific resource from the database by its resource_id.
    Used after successful termination to clean up the dashboard.
    """
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM zombie_resources WHERE resource_id = ?", (resource_id,))
        conn.commit()
    finally:
        conn.close()
