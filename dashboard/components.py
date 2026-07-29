from __future__ import annotations
"""
dashboard/components.py
========================
Premium UI components for Ghost Resource Exterminator.
Expert-level design with glassmorphism, animated cards, and professional table.
"""

import streamlit as st  # type: ignore
import streamlit.components.v1 as stc  # type: ignore
import pandas as pd  # type: ignore
from typing import Optional, Union


GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Reset & Base ─────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: #060612 !important;
    color: #e2e2f0 !important;
}

/* ── Sidebar ────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0a1a 0%, #0d0d20 100%) !important;
    border-right: 1px solid rgba(108, 71, 255, 0.2) !important;
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] > div { padding-top: 0 !important; }
section[data-testid="stSidebar"] * { color: #c8c8e8 !important; }

/* ── Main container ─────────────────────────── */
.main .block-container {
    padding: 1.5rem 2rem 3rem 2rem !important;
    max-width: 1400px !important;
    background: #060612 !important;
}

/* ── Buttons ─────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #6c47ff 0%, #9d4edd 100%) !important;
    color: #fff !important;
    border: 1px solid rgba(108,71,255,0.4) !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.6rem 1.2rem !important;
    letter-spacing: 0.01em !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 4px 15px rgba(108,71,255,0.25) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(108,71,255,0.45) !important;
    border-color: rgba(108,71,255,0.7) !important;
}
.stButton > button:active { transform: translateY(0px) !important; }

/* ── Selectbox ───────────────────────────────── */
.stSelectbox > label {
    color: #8888bb !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
.stSelectbox > div > div {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(108,71,255,0.2) !important;
    border-radius: 8px !important;
    color: #e2e2f0 !important;
}
.stSelectbox > div > div:hover {
    border-color: rgba(108,71,255,0.5) !important;
}

/* ── TextInput ───────────────────────────────── */
.stTextInput > label {
    color: #8888bb !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(108,71,255,0.2) !important;
    border-radius: 8px !important;
    color: #e2e2f0 !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.stTextInput > div > div > input:focus {
    border-color: rgba(108,71,255,0.6) !important;
    box-shadow: 0 0 0 3px rgba(108,71,255,0.15) !important;
}

/* ── Spinner ────────────────────────────────── */
.stSpinner > div { border-top-color: #6c47ff !important; }

/* ── Alert / Warning ────────────────────────── */
.stAlert {
    background: rgba(255, 193, 7, 0.08) !important;
    border: 1px solid rgba(255, 193, 7, 0.25) !important;
    border-radius: 10px !important;
    color: #ffc107 !important;
}

/* ── Scrollbar ──────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0a0a1a; }
::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4a4a8a; }

/* ── Divider ────────────────────────────────── */
hr { border: none !important; border-top: 1px solid rgba(108,71,255,0.12) !important; margin: 1.5rem 0 !important; }

/* ── Plotly ─────────────────────────────────── */
.js-plotly-plot .plotly, .js-plotly-plot .plotly .svg-container { background: transparent !important; }

/* ── Success / Info / Error ─────────────────── */
.element-container .stSuccess {
    background: rgba(33, 197, 93, 0.08) !important;
    border: 1px solid rgba(33,197,93,0.25) !important;
    border-radius: 10px !important;
}
.element-container .stError {
    background: rgba(255, 75, 75, 0.08) !important;
    border: 1px solid rgba(255,75,75,0.25) !important;
    border-radius: 10px !important;
}

/* ── Headings ───────────────────────────────── */
h1, h2, h3 { font-family: 'Inter', sans-serif !important; }
h2 { color: #bd93f9 !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
h3 { color: #9d8fc0 !important; font-weight: 600 !important; letter-spacing: -0.01em !important; }
</style>
"""


def render_global_css() -> None:
    """Injects global CSS styles into the Streamlit page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_sidebar_logo() -> None:
    """Renders the premium sidebar header with logo, version badge, and status indicator."""
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, rgba(108,71,255,0.15), rgba(157,78,221,0.08));
            border-bottom: 1px solid rgba(108,71,255,0.2);
            padding: 24px 20px 20px 20px;
            margin: -1rem -1rem 1.5rem -1rem;
        ">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                <span style="font-size:1.8rem; line-height:1;">🎯</span>
                <div>
                    <div style="font-size:1rem; font-weight:800; color:#e2e2f0; letter-spacing:-0.02em;">
                        Ghost Exterminator
                    </div>
                    <div style="font-size:0.7rem; color:#6c6c8a; letter-spacing:0.05em; margin-top:1px;">
                        AWS FinOps Dashboard
                    </div>
                </div>
            </div>
            <div style="display:flex; gap:6px; margin-top:10px; flex-wrap:wrap;">
                <span style="background:rgba(108,71,255,0.2);color:#9d8fc0;border:1px solid rgba(108,71,255,0.3);
                             border-radius:20px;padding:2px 10px;font-size:0.65rem;font-weight:600;letter-spacing:0.05em;">
                    v2.0
                </span>
                <span style="background:rgba(33,197,93,0.12);color:#21c55d;border:1px solid rgba(33,197,93,0.25);
                             border-radius:20px;padding:2px 10px;font-size:0.65rem;font-weight:600;letter-spacing:0.05em;">
                    ● LIVE
                </span>
                <span style="background:rgba(139,233,253,0.08);color:#8be9fd;border:1px solid rgba(139,233,253,0.2);
                             border-radius:20px;padding:2px 10px;font-size:0.65rem;font-weight:600;letter-spacing:0.05em;">
                    MULTI-REGION
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_section(title: str) -> None:
    """Renders a styled sidebar section label."""
    st.markdown(
        f"""<div style="font-size:0.68rem;font-weight:700;color:#4a4a7a;letter-spacing:0.12em;
                       text-transform:uppercase;margin:16px 0 8px 0;padding-bottom:4px;
                       border-bottom:1px solid rgba(108,71,255,0.1);">{title}</div>""",
        unsafe_allow_html=True,
    )


def render_page_header(last_scan: Optional[str] = None) -> None:
    """Renders the main dashboard hero header."""
    scan_info = (
        f"🕐 Last scan: <b style='color:#6c6c9a;'>{last_scan}</b>"
        if last_scan
        else "🕐 No scan data — configure <b>.env</b> credentials and click <b style='color:#6c47ff'>Run Scan</b>"
    )
    st.markdown(
        f"""<div style="background:linear-gradient(135deg,rgba(108,71,255,0.12) 0%,rgba(13,7,30,0.8) 40%,rgba(157,78,221,0.08) 100%);border:1px solid rgba(108,71,255,0.18);border-radius:20px;padding:28px 36px;margin-bottom:20px;">
<div style="display:flex;align-items:center;gap:14px;">
<span style="font-size:2.5rem;">🎯</span>
<div>
<div style="font-size:2rem;font-weight:900;background:linear-gradient(135deg,#ffffff 0%,#c4b5fd 50%,#a78bfa 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.03em;">Ghost Resource Exterminator</div>
<div style="font-size:0.88rem;color:#6c6c9a;margin-top:2px;">Identify &amp; eliminate zombie AWS resources draining your cloud budget</div>
</div></div>
<div style="font-size:0.75rem;color:#4a4a6a;margin-top:10px;">{scan_info}</div>
</div>""",
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: Union[int, str], icon: str, color: str, subtitle: str = "") -> None:
    """Renders a glassmorphism metric card with glow effect."""
    subtitle_html = (
        f'<div style="font-size:0.68rem;color:#4a4a6a;margin-top:4px;font-weight:500;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%);
            border: 1px solid rgba({_hex_to_rgb(color)}, 0.22);
            border-radius: 16px;
            padding: 20px 22px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            cursor: default;
        ">
            <!-- Glow accent -->
            <div style="
                position:absolute; top:0; left:0; right:0; height:2px;
                background: linear-gradient(90deg, transparent, {color}, transparent);
                border-radius: 16px 16px 0 0;
            "></div>
            <!-- Corner glow -->
            <div style="
                position:absolute; top:-30px; right:-30px;
                width:100px; height:100px;
                background: radial-gradient(circle, rgba({_hex_to_rgb(color)},0.1) 0%, transparent 70%);
                border-radius:50%;
            "></div>
            <div style="position:relative; z-index:1;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                    <span style="font-size:1.4rem;">{icon}</span>
                </div>
                <div style="font-size:2rem; font-weight:800; color:{color}; line-height:1; letter-spacing:-0.03em;">
                    {value}
                </div>
                <div style="font-size:0.7rem; color:#5a5a7a; margin-top:5px; font-weight:600;
                            letter-spacing:0.09em; text-transform:uppercase;">{label}</div>
                {subtitle_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hex_to_rgb(hex_color: str) -> str:
    """Converts '#rrggbb' to 'r,g,b' string for rgba()."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)  # type: ignore[index]
    return f"{r},{g},{b}"


def render_status_badge(status: str) -> str:
    """Returns styled HTML badge for resource status."""
    if status == "Zombie":
        return (
            '<span style="background:rgba(255,75,75,0.12);color:#ff4b4b;'
            'border:1px solid rgba(255,75,75,0.3);border-radius:20px;'
            'padding:2px 10px;font-size:0.7rem;font-weight:700;white-space:nowrap;">'
            "🎯 Zombie</span>"
        )
    return (
        '<span style="background:rgba(33,197,93,0.1);color:#21c55d;'
        'border:1px solid rgba(33,197,93,0.25);border-radius:20px;'
        'padding:2px 10px;font-size:0.7rem;font-weight:700;white-space:nowrap;">'
        "✅ Active</span>"
    )


def render_type_badge(rtype: str) -> str:
    """Returns a coloured badge for resource type."""
    configs = {
        "EC2":           ("#8be9fd", "rgba(139,233,253,0.08)", "rgba(139,233,253,0.2)", "💻"),
        "EBS":           ("#f1fa8c", "rgba(241,250,140,0.08)", "rgba(241,250,140,0.2)", "💽"),
        "Snapshot":      ("#c56cf0", "rgba(197,108,240,0.08)", "rgba(197,108,240,0.2)", "📸"),
        "EIP":           ("#ff79c6", "rgba(255,121,198,0.08)", "rgba(255,121,198,0.2)", "🌐"),
        "ELB":           ("#ff5555", "rgba(255,85,85,0.08)", "rgba(255,85,85,0.2)", "⚖️"),
        "SecurityGroup": ("#50fa7b", "rgba(80,250,123,0.08)", "rgba(80,250,123,0.2)", "🛡️"),
        "AMI":           ("#ffb86c", "rgba(255,184,108,0.08)", "rgba(255,184,108,0.2)", "💾"),
        "StoppedEC2":    ("#ff5555", "rgba(255,85,85,0.08)", "rgba(255,85,85,0.2)", "🛑"),
        "EFS":           ("#8be9fd", "rgba(139,233,253,0.08)", "rgba(139,233,253,0.2)", "📁"),
        "NATGateway":    ("#f1fa8c", "rgba(241,250,140,0.08)", "rgba(241,250,140,0.2)", "🔌"),
    }
    color, bg, border, icon = configs.get(rtype, ("#aaa", "rgba(170,170,170,0.08)", "rgba(170,170,170,0.2)", "📦"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {border};'
        f'border-radius:6px;padding:2px 9px;font-size:0.7rem;font-weight:600;">'
        f'{icon} {rtype}</span>'
    )


def render_resource_table(df: pd.DataFrame) -> None:
    """Renders a simple, clean resource table using Streamlit dataframe."""
    if df.empty:
        st.info("No resources match the current filters.")
        return

    display_df = df[["resource_id", "resource_type", "region", "utilization", "status", "reason", "detected_at"]].copy()
    display_df.columns = ["Resource ID", "Type", "Region", "Utilization", "Status", "Reason", "Detected"]
    display_df["Utilization"] = display_df.apply(
        lambda r: f"{r['Utilization']:.2f}%" if r["Type"] == "EC2" else "N/A", axis=1
    )
    display_df["Detected"] = display_df["Detected"].astype(str).str[:16].str.replace("T", " ")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(400, 38 + len(display_df) * 35),
    )


def render_section_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Renders a professional section header with optional subtitle."""
    st.markdown(
        f"""
        <div style="margin: 28px 0 16px 0;">
            <div style="display:flex; align-items:center; gap:10px;">
                {f'<span style="font-size:1.2rem;">{icon}</span>' if icon else ''}
                <div>
                    <h2 style="margin:0; font-size:1.1rem; font-weight:700; color:#c4b5fd;
                               letter-spacing:-0.01em;">{title}</h2>
                    {f'<p style="margin:2px 0 0 0; font-size:0.78rem; color:#4a4a6a;">{subtitle}</p>' if subtitle else ''}
                </div>
            </div>
            <div style="height:1px; background:linear-gradient(90deg,rgba(108,71,255,0.3),transparent);
                        margin-top:10px; border-radius:1px;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    """Premium empty state prompting the user to connect their AWS account."""
    st.markdown(
        """
        <div style="
            text-align: center;
            padding: 80px 30px;
            background: rgba(255,255,255,0.015);
            border-radius: 20px;
            border: 1px dashed rgba(108,71,255,0.2);
            margin: 20px 0;
            position: relative;
            overflow: hidden;
        ">
            <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                        width:400px;height:400px;
                        background:radial-gradient(circle,rgba(108,71,255,0.06) 0%,transparent 70%);
                        border-radius:50%;pointer-events:none;"></div>
            <div style="position:relative;z-index:1;">
                <div style="font-size:3.5rem;margin-bottom:16px;filter:drop-shadow(0 0 20px rgba(108,71,255,0.4));">☁️</div>
                <h3 style="color:#c4b5fd;margin:0 0 8px;font-size:1.3rem;font-weight:700;">No AWS Data Yet</h3>
                <p style="color:#4a4a7a;margin:0 0 24px;font-size:0.875rem;line-height:1.7;max-width:400px;margin-left:auto;margin-right:auto;">
                    Connect your AWS account and run a live scan to detect zombie resources wasting your budget.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
