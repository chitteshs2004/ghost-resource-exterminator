"""
report_generator.py
===================
Ghost Resource Exterminator — Rich HTML Report Generator.

Builds a fully self-contained, branded HTML report from scan data:
  - All CSS is inlined (no external dependencies)
  - Plotly charts are embedded as base64 PNG images
  - Full resource table with status / type badges
  - Summary cards, regional breakdown, cost-savings estimate

Public API
----------
    generate_report_bundle(df, stats, account_id, region, zombies_only, include_charts)
        → {"html": bytes, "csv": bytes, "filename_prefix": str}
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd  # type: ignore


# ── Cost-savings estimate (very rough monthly $ per resource type) ─────────────
_MONTHLY_COST_ESTIMATES: dict[str, float] = {
    "EC2":           45.00,
    "EBS":           10.00,
    "Snapshot":       2.50,
    "EIP":            3.60,
    "ELB":           18.00,
    "SecurityGroup":  0.00,
    "AMI":            1.50,
    "StoppedEC2":    12.00,
    "EFS":            8.00,
    "NATGateway":    35.00,
}


# ── Chart helpers ──────────────────────────────────────────────────────────────

def _fig_to_base64_png(fig, width: int = 700, height: int = 340) -> str:
    """Converts a Plotly figure to a base64-encoded PNG data URI."""
    try:
        import plotly.io as pio  # type: ignore
        png_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=2)
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


def _build_donut_chart(df: pd.DataFrame) -> str:
    """Status split donut chart → base64 PNG data URI."""
    try:
        import plotly.graph_objects as go  # type: ignore

        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]

        fig = go.Figure(go.Pie(
            labels=status_counts["Status"],
            values=status_counts["Count"],
            hole=0.60,
            marker={
                "colors": ["#ff4b4b" if s == "Zombie" else "#21c55d"
                           for s in status_counts["Status"]],
                "line": {"color": "#0d0d20", "width": 3},
            },
            textinfo="percent+label",
            textfont={"family": "Inter", "size": 13, "color": "#e2e2f0"},
        ))
        zombie_n = int(status_counts.loc[
            status_counts["Status"] == "Zombie", "Count"].sum())
        fig.add_annotation(
            text=f"<b>{zombie_n}</b><br><span style='font-size:10px'>zombies</span>",
            x=0.5, y=0.5, showarrow=False,
            font={"size": 20, "color": "#ff4b4b", "family": "Inter"},
            align="center",
        )
        fig.update_layout(
            paper_bgcolor="rgba(13,13,32,1)",
            plot_bgcolor="rgba(13,13,32,1)",
            font={"color": "#9090b0", "family": "Inter"},
            margin={"t": 30, "b": 30, "l": 20, "r": 20},
            title={"text": "Resource Status Split",
                   "font": {"color": "#c4b5fd", "size": 14}, "x": 0.5},
            legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#9090b0"},
                    "orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.05},
            showlegend=True,
        )
        return _fig_to_base64_png(fig, 600, 340)
    except Exception:
        return ""


def _build_bar_chart(df: pd.DataFrame) -> str:
    """Resources by type & status grouped bar → base64 PNG data URI."""
    try:
        import plotly.express as px  # type: ignore

        type_status = df.groupby(["resource_type", "status"]).size().reset_index(name="count")
        fig = px.bar(
            type_status, x="resource_type", y="count", color="status",
            barmode="group",
            color_discrete_map={"Zombie": "#ff4b4b", "Active": "#21c55d"},
            labels={"resource_type": "", "count": "Count", "status": ""},
            text="count",
        )
        fig.update_traces(
            textposition="outside",
            textfont={"color": "#9090b0", "size": 11},
            marker={"line": {"width": 0}},
        )
        fig.update_layout(
            paper_bgcolor="rgba(13,13,32,1)",
            plot_bgcolor="rgba(13,13,32,1)",
            font={"color": "#9090b0", "family": "Inter"},
            xaxis={"gridcolor": "rgba(108,71,255,0.08)",
                   "tickfont": {"color": "#6060a0", "size": 11}},
            yaxis={"gridcolor": "rgba(108,71,255,0.08)",
                   "tickfont": {"color": "#6060a0", "size": 11}, "title": ""},
            legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#9090b0"},
                    "orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.15},
            margin={"t": 40, "b": 20, "l": 20, "r": 20},
            bargap=0.25, bargroupgap=0.08,
            title={"text": "Resources by Type & Status",
                   "font": {"color": "#c4b5fd", "size": 14}, "x": 0.5},
        )
        return _fig_to_base64_png(fig, 700, 340)
    except Exception:
        return ""


def _build_region_chart(df: pd.DataFrame) -> str:
    """Regional zombie distribution horizontal bar → base64 PNG data URI."""
    try:
        import plotly.graph_objects as go  # type: ignore

        region_zombie = (
            df[df["status"] == "Zombie"]
            .groupby("region").size().reset_index(name="Zombie Count")
            .sort_values("Zombie Count", ascending=True)
        )
        if region_zombie.empty:
            return ""

        fig = go.Figure(go.Bar(
            y=region_zombie["region"],
            x=region_zombie["Zombie Count"],
            orientation="h",
            marker={
                "color": region_zombie["Zombie Count"],
                "colorscale": [[0, "#1a0a2e"], [0.5, "#6c47ff"], [1, "#ff4b4b"]],
                "line": {"width": 0},
            },
            text=region_zombie["Zombie Count"],
            textposition="outside",
            textfont={"color": "#9090b0", "size": 11},
        ))
        fig.update_layout(
            paper_bgcolor="rgba(13,13,32,1)",
            plot_bgcolor="rgba(13,13,32,1)",
            font={"color": "#9090b0", "family": "Inter"},
            xaxis={"gridcolor": "rgba(108,71,255,0.08)",
                   "tickfont": {"color": "#6060a0"}},
            yaxis={"gridcolor": "rgba(0,0,0,0)",
                   "tickfont": {"color": "#8080b0", "size": 11}},
            margin={"t": 40, "b": 20, "l": 20, "r": 40},
            height=max(200, len(region_zombie) * 40),
            title={"text": "Zombie Distribution by Region",
                   "font": {"color": "#c4b5fd", "size": 14}, "x": 0.5},
        )
        return _fig_to_base64_png(fig, 700, max(220, len(region_zombie) * 40))
    except Exception:
        return ""


# ── Cost estimate helper ───────────────────────────────────────────────────────

def _estimate_monthly_savings(df: pd.DataFrame) -> float:
    """Rough monthly USD savings if all zombies in df are eliminated."""
    zombies = df[df["status"] == "Zombie"]
    total = 0.0
    for rtype, grp in zombies.groupby("resource_type"):
        total += len(grp) * _MONTHLY_COST_ESTIMATES.get(str(rtype), 0.0)
    return total


# ── HTML template ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Ghost Resource Exterminator — Scan Report</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',sans-serif;background:#060612;color:#e2e2f0;min-height:100vh;padding:0}}
a{{color:#8b5cf6;text-decoration:none}}

/* ── Header ── */
.header{{background:linear-gradient(135deg,rgba(108,71,255,0.18) 0%,rgba(13,7,30,0.95) 50%,rgba(157,78,221,0.12) 100%);
         border-bottom:1px solid rgba(108,71,255,0.25);padding:36px 48px 32px}}
.header-top{{display:flex;align-items:center;gap:16px;margin-bottom:20px}}
.logo{{font-size:2.8rem;filter:drop-shadow(0 0 20px rgba(255,153,0,0.5))}}
.title{{font-size:2rem;font-weight:900;letter-spacing:-0.03em;
        background:linear-gradient(135deg,#ffffff 0%,#c4b5fd 50%,#a78bfa 100%);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.subtitle{{font-size:0.85rem;color:#6c6c9a;margin-top:4px}}
.meta-row{{display:flex;flex-wrap:wrap;gap:20px;font-size:0.78rem;color:#5a5a7a}}
.meta-item{{display:flex;align-items:center;gap:6px}}
.meta-label{{color:#4a4a6a;font-weight:600;letter-spacing:0.06em;text-transform:uppercase}}
.meta-value{{color:#9090b0;font-family:'JetBrains Mono',monospace}}

/* ── Content ── */
.content{{max-width:1200px;margin:0 auto;padding:32px 48px 60px}}

/* ── Section header ── */
.section-header{{margin:36px 0 18px;display:flex;align-items:center;gap:10px}}
.section-icon{{font-size:1.2rem}}
.section-title{{font-size:1.05rem;font-weight:700;color:#c4b5fd;letter-spacing:-0.01em}}
.section-sub{{font-size:0.78rem;color:#4a4a6a;margin-top:2px}}
.section-divider{{height:1px;background:linear-gradient(90deg,rgba(108,71,255,0.35),transparent);
                  margin-top:8px;border-radius:1px}}

/* ── Summary Cards ── */
.cards-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin-bottom:8px}}
.card{{background:linear-gradient(145deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
       border-radius:14px;padding:18px 20px;position:relative;overflow:hidden}}
.card-glow-top{{position:absolute;top:0;left:0;right:0;height:2px;border-radius:14px 14px 0 0}}
.card-value{{font-size:1.9rem;font-weight:800;line-height:1;letter-spacing:-0.03em}}
.card-label{{font-size:0.65rem;color:#5a5a7a;margin-top:5px;font-weight:600;
             letter-spacing:0.09em;text-transform:uppercase}}
.card-subtitle{{font-size:0.65rem;color:#4a4a6a;margin-top:3px}}
.card-icon{{font-size:1.3rem;margin-bottom:6px}}

/* ── Charts ── */
.charts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:8px}}
.chart-box{{background:rgba(255,255,255,0.015);border:1px solid rgba(108,71,255,0.12);
            border-radius:16px;padding:12px;overflow:hidden}}
.chart-box.full{{grid-column:1/-1}}
.chart-box img{{width:100%;height:auto;border-radius:8px;display:block}}

/* ── Resource Table ── */
.table-wrap{{overflow-x:auto;border-radius:14px;border:1px solid rgba(108,71,255,0.12)}}
table{{width:100%;border-collapse:collapse;font-size:0.8rem}}
thead tr{{background:rgba(108,71,255,0.1)}}
thead th{{padding:12px 14px;text-align:left;font-size:0.67rem;font-weight:700;
          color:#6060a0;letter-spacing:0.09em;text-transform:uppercase;
          border-bottom:1px solid rgba(108,71,255,0.15);white-space:nowrap}}
tbody tr{{border-bottom:1px solid rgba(108,71,255,0.06);transition:background 0.15s}}
tbody tr:hover{{background:rgba(108,71,255,0.04)}}
tbody tr:last-child{{border-bottom:none}}
tbody td{{padding:10px 14px;color:#c8c8e8;vertical-align:middle}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#8be9fd}}
.badge{{display:inline-block;border-radius:20px;padding:2px 10px;
        font-size:0.68rem;font-weight:700;white-space:nowrap}}
.badge-zombie{{background:rgba(255,75,75,0.12);color:#ff4b4b;border:1px solid rgba(255,75,75,0.3)}}
.badge-active{{background:rgba(33,197,93,0.10);color:#21c55d;border:1px solid rgba(33,197,93,0.25)}}
.badge-type{{border-radius:6px;padding:2px 9px;font-size:0.68rem;font-weight:600}}
.reason-text{{font-size:0.73rem;color:#5a5a8a;max-width:300px;line-height:1.4}}

/* ── Cost Banner ── */
.cost-banner{{background:linear-gradient(135deg,rgba(33,197,93,0.08),rgba(108,71,255,0.06));
              border:1px solid rgba(33,197,93,0.2);border-radius:14px;
              padding:20px 28px;display:flex;align-items:center;gap:18px;margin-bottom:8px}}
.cost-icon{{font-size:2rem}}
.cost-amount{{font-size:2rem;font-weight:900;color:#21c55d;letter-spacing:-0.03em}}
.cost-label{{font-size:0.75rem;color:#4a4a7a;margin-top:2px}}
.cost-note{{font-size:0.72rem;color:#3a3a5a;margin-top:4px;font-style:italic}}

/* ── Footer ── */
.footer{{background:rgba(0,0,0,0.3);border-top:1px solid rgba(108,71,255,0.1);
         padding:20px 48px;display:flex;justify-content:space-between;
         align-items:center;font-size:0.72rem;color:#3a3a5a;flex-wrap:wrap;gap:8px}}
.footer-brand{{color:#6c47ff;font-weight:700}}

/* ── Responsive ── */
@media(max-width:700px){{
  .header,.content{{padding-left:20px;padding-right:20px}}
  .charts-grid{{grid-template-columns:1fr}}
  .charts-grid .chart-box.full{{grid-column:auto}}
}}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<div class="header">
  <div class="header-top">
    <div class="logo">🎯</div>
    <div>
      <div class="title">Ghost Resource Exterminator</div>
      <div class="subtitle">AWS Cloud FinOps — Zombie Resource Scan Report</div>
    </div>
  </div>
  <div class="meta-row">
    <div class="meta-item">
      <span class="meta-label">Account</span>
      <span class="meta-value">{account_id}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Region</span>
      <span class="meta-value">{region}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Generated</span>
      <span class="meta-value">{generated_at}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Resources</span>
      <span class="meta-value">{total_count} scanned · {zombie_count} zombies</span>
    </div>
  </div>
</div>

<div class="content">

  <!-- ═══ COST SAVINGS ═══ -->
  {cost_banner_html}

  <!-- ═══ SUMMARY CARDS ═══ -->
  <div class="section-header">
    <span class="section-icon">📊</span>
    <div>
      <div class="section-title">Summary</div>
      <div class="section-sub">Aggregate counts from the latest scan</div>
    </div>
  </div>
  <div class="section-divider"></div>
  <br/>
  <div class="cards-grid">
    {cards_html}
  </div>

  <!-- ═══ CHARTS ═══ -->
  {charts_html}

  <!-- ═══ RESOURCE TABLE ═══ -->
  <div class="section-header">
    <span class="section-icon">🗂️</span>
    <div>
      <div class="section-title">Resource Inventory</div>
      <div class="section-sub">{table_subtitle}</div>
    </div>
  </div>
  <div class="section-divider"></div>
  <br/>
  <div class="table-wrap">
    {table_html}
  </div>

</div>

<!-- ═══ FOOTER ═══ -->
<div class="footer">
  <div>🎯 <span class="footer-brand">Ghost Resource Exterminator</span> &nbsp;·&nbsp; Python · Boto3 · CloudWatch · Streamlit</div>
  <div>💰 Reduce cloud waste &nbsp;·&nbsp; 🌍 Multi-region &nbsp;·&nbsp; 🔒 Secure by default</div>
</div>

</body>
</html>
"""


# ── Type badge colors ──────────────────────────────────────────────────────────
_TYPE_BADGE_STYLES: dict[str, tuple[str, str]] = {
    "EC2":           ("#8be9fd", "rgba(139,233,253,0.1)"),
    "EBS":           ("#f1fa8c", "rgba(241,250,140,0.1)"),
    "Snapshot":      ("#c56cf0", "rgba(197,108,240,0.1)"),
    "EIP":           ("#ff79c6", "rgba(255,121,198,0.1)"),
    "ELB":           ("#ff5555", "rgba(255,85,85,0.1)"),
    "SecurityGroup": ("#50fa7b", "rgba(80,250,123,0.1)"),
    "AMI":           ("#ffb86c", "rgba(255,184,108,0.1)"),
    "StoppedEC2":    ("#ff5555", "rgba(255,85,85,0.1)"),
    "EFS":           ("#8be9fd", "rgba(139,233,253,0.1)"),
    "NATGateway":    ("#f1fa8c", "rgba(241,250,140,0.1)"),
}

_TYPE_ICONS: dict[str, str] = {
    "EC2": "💻", "EBS": "💽", "Snapshot": "📸", "EIP": "🌐",
    "ELB": "⚖️", "SecurityGroup": "🛡️", "AMI": "💾",
    "StoppedEC2": "🛑", "EFS": "📁", "NATGateway": "🔌",
}

_CARD_CONFIGS: dict[str, tuple[str, str, str]] = {
    "EC2":           ("#ff9f43", "💻", "EC2 Zombies"),
    "EBS":           ("#f1fa8c", "💽", "EBS Zombies"),
    "Snapshot":      ("#c56cf0", "📸", "Snapshot Zombies"),
    "EIP":           ("#ff79c6", "🌐", "EIP Zombies"),
    "ELB":           ("#ff5555", "⚖️", "ELB Zombies"),
    "SecurityGroup": ("#50fa7b", "🛡️", "SG Zombies"),
    "AMI":           ("#ffb86c", "💾", "AMI Zombies"),
    "StoppedEC2":    ("#ff5555", "🛑", "Stopped EC2s"),
    "EFS":           ("#8be9fd", "📁", "EFS Zombies"),
    "NATGateway":    ("#f1fa8c", "🔌", "NATG Zombies"),
}


def _build_card(label: str, value: Any, icon: str, color: str,
                subtitle: str = "") -> str:
    sub = (f'<div class="card-subtitle">{subtitle}</div>' if subtitle else "")
    return f"""
    <div class="card" style="border:1px solid {color}33;">
      <div class="card-glow-top" style="background:linear-gradient(90deg,transparent,{color},transparent);"></div>
      <div class="card-icon">{icon}</div>
      <div class="card-value" style="color:{color};">{value}</div>
      <div class="card-label">{label}</div>
      {sub}
    </div>"""


def _build_cards_html(df: pd.DataFrame, stats: dict[str, Any]) -> str:
    total   = stats.get("total", len(df))
    zombie  = stats.get("zombie", int((df["status"] == "Zombie").sum()))
    active  = stats.get("active", int((df["status"] == "Active").sum()))
    zombie_pct = round(zombie / total * 100) if total else 0

    cards = [
        _build_card("Total Scanned",    total,  "📦", "#8be9fd", "across all regions"),
        _build_card("Zombie Resources", zombie, "🧟", "#ff4b4b", f"{zombie_pct}% of total"),
        _build_card("Active Resources", active, "✅", "#21c55d", "healthy resources"),
    ]
    for rtype, (color, icon, label) in _CARD_CONFIGS.items():
        key = f"{rtype.lower()}_zombie"
        count = stats.get(key, 0)
        if count > 0:
            cards.append(_build_card(label, count, icon, color))

    return "\n".join(cards)


def _build_charts_html(df: pd.DataFrame, include_charts: bool) -> str:
    if not include_charts or df.empty:
        return ""

    donut_src  = _build_donut_chart(df)
    bar_src    = _build_bar_chart(df)
    region_src = _build_region_chart(df) if df["region"].nunique() > 1 else ""

    donut_img  = f'<img src="{donut_src}" alt="Status split chart"/>'  if donut_src  else "<p style='color:#5a5a7a;text-align:center;padding:40px'>Chart unavailable</p>"
    bar_img    = f'<img src="{bar_src}" alt="Type breakdown chart"/>'   if bar_src    else ""
    region_img = f'<img src="{region_src}" alt="Regional breakdown"/>'  if region_src else ""

    region_block = (
        f"""
        <div class="section-header" style="margin-top:28px">
          <span class="section-icon">🌍</span>
          <div>
            <div class="section-title">Regional Breakdown</div>
            <div class="section-sub">Zombie distribution across AWS regions</div>
          </div>
        </div>
        <div class="section-divider"></div><br/>
        <div class="chart-box full">{region_img}</div>
        """
        if region_img else ""
    )

    return f"""
    <div class="section-header" style="margin-top:28px">
      <span class="section-icon">📈</span>
      <div>
        <div class="section-title">Analytics</div>
        <div class="section-sub">Visual breakdown of your scanned resources</div>
      </div>
    </div>
    <div class="section-divider"></div><br/>
    <div class="charts-grid">
      <div class="chart-box">{donut_img}</div>
      <div class="chart-box">{bar_img}</div>
    </div>
    {region_block}
    """


def _build_table_html(df: pd.DataFrame) -> str:
    """Builds a styled HTML table from the DataFrame."""
    if df.empty:
        return "<p style='color:#5a5a7a;padding:20px;text-align:center;'>No resources to display.</p>"

    rows_html = []
    for _, row in df.iterrows():
        status = str(row.get("status", ""))
        rtype  = str(row.get("resource_type", ""))
        rid    = str(row.get("resource_id", ""))
        region = str(row.get("region", ""))
        reason = str(row.get("reason", ""))
        detected = str(row.get("detected_at", ""))[:16].replace("T", " ")

        util_raw = row.get("utilization", 0.0)
        util_str = f"{float(util_raw):.2f}%" if rtype == "EC2" else "N/A"

        status_badge = (
            '<span class="badge badge-zombie">🎯 Zombie</span>'
            if status == "Zombie"
            else '<span class="badge badge-active">✅ Active</span>'
        )

        tc, bg = _TYPE_BADGE_STYLES.get(rtype, ("#aaa", "rgba(170,170,170,0.08)"))
        icon   = _TYPE_ICONS.get(rtype, "📦")
        type_badge = (
            f'<span class="badge badge-type" '
            f'style="color:{tc};background:{bg};border:1px solid {tc}44;">'
            f'{icon} {rtype}</span>'
        )

        rows_html.append(f"""
        <tr>
          <td><span class="mono">{rid}</span></td>
          <td>{type_badge}</td>
          <td><span style="color:#8080b0;font-size:0.77rem;">{region}</span></td>
          <td><span style="color:#ff9f43;">{util_str}</span></td>
          <td>{status_badge}</td>
          <td><span class="reason-text">{reason}</span></td>
          <td><span style="color:#5a5a7a;font-size:0.73rem;font-family:'JetBrains Mono',monospace;">{detected}</span></td>
        </tr>""")

    header = """
    <table>
      <thead>
        <tr>
          <th>Resource ID</th>
          <th>Type</th>
          <th>Region</th>
          <th>Utilization</th>
          <th>Status</th>
          <th>Reason</th>
          <th>Detected At</th>
        </tr>
      </thead>
      <tbody>
    """
    return header + "\n".join(rows_html) + "\n  </tbody>\n</table>"


def _build_cost_banner(savings: float) -> str:
    if savings <= 0:
        return ""
    return f"""
    <div class="cost-banner">
      <div class="cost-icon">💰</div>
      <div>
        <div class="cost-amount">${savings:,.0f} / mo</div>
        <div class="cost-label">Estimated monthly savings if all zombies are eliminated</div>
        <div class="cost-note">Based on rough per-resource-type average costs. Actual savings may vary.</div>
      </div>
    </div>
    <br/>
    """


# ── Public API ────────────────────────────────────────────────────────────────

def generate_html_report(
    df: pd.DataFrame,
    stats: dict[str, Any],
    account_id: str = "unknown",
    region: str = "multi-region",
    zombies_only: bool = False,
    include_charts: bool = True,
) -> str:
    """
    Builds a fully self-contained HTML report string.

    Args:
        df:            Full or filtered scan DataFrame.
        stats:         Summary stats dict from get_summary_stats().
        account_id:    AWS Account ID (used in the header).
        region:        Region label string.
        zombies_only:  If True, only zombie rows appear in the resource table.
        include_charts: If True, Plotly charts are embedded as base64 PNG.

    Returns:
        HTML string — self-contained, no external dependencies.
    """
    if df is None or df.empty:
        return "<html><body><p>No scan data available.</p></body></html>"

    # Decide which rows appear in the table
    table_df = df[df["status"] == "Zombie"].copy() if zombies_only else df.copy()

    # Ensure numeric utilization
    table_df["utilization"] = pd.to_numeric(
        table_df.get("utilization", 0), errors="coerce"
    ).fillna(0.0)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_count  = stats.get("total", len(df))
    zombie_count = stats.get("zombie", int((df["status"] == "Zombie").sum()))
    savings      = _estimate_monthly_savings(df)
    table_subtitle = (
        f"{len(table_df)} zombie resources"
        if zombies_only
        else f"{len(table_df)} total resources · {zombie_count} zombies"
    )

    html = _HTML_TEMPLATE.format(
        account_id      = account_id,
        region          = region,
        generated_at    = generated_at,
        total_count     = total_count,
        zombie_count    = zombie_count,
        cost_banner_html= _build_cost_banner(savings),
        cards_html      = _build_cards_html(df, stats),
        charts_html     = _build_charts_html(df, include_charts),
        table_subtitle  = table_subtitle,
        table_html      = _build_table_html(table_df),
    )
    return html


def generate_report_bundle(
    df: pd.DataFrame,
    stats: dict[str, Any],
    account_id: str = "unknown",
    region: str = "multi-region",
    zombies_only: bool = False,
    include_charts: bool = True,
) -> dict[str, Any]:
    """
    Generates a report bundle ready for download or S3 upload.

    Returns:
        {
            "html":             bytes  — self-contained HTML report,
            "csv":              bytes  — raw CSV data,
            "filename_prefix":  str    — e.g. "2026-06-14_08-49-00"
        }
    """
    html_str = generate_html_report(
        df, stats, account_id, region, zombies_only, include_charts
    )
    csv_df = df[df["status"] == "Zombie"].copy() if zombies_only else df.copy()
    if "detected_at" in csv_df.columns:
        csv_df["detected_at"] = csv_df["detected_at"].astype(str)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return {
        "html":            html_str.encode("utf-8"),
        "csv":             csv_df.to_csv(index=False).encode("utf-8"),
        "filename_prefix": ts,
    }
