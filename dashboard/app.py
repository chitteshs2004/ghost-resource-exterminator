"""
dashboard/app.py
================
Ghost Resource Exterminator — Premium Streamlit Dashboard.
Glassmorphism UI · Plotly analytics · Live AWS scanning · Multi-region.
"""

from __future__ import annotations
import sys
import os

# ── Path Setup (before all local imports) ─────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st          # type: ignore
import pandas as pd             # type: ignore
import plotly.express as px     # type: ignore
import plotly.graph_objects as go  # type: ignore

from db import (                # type: ignore
    get_all_resources,
    get_summary_stats,
    init_db,
    delete_resource,
    clear_resources,
    reset_db,
)
from dashboard.components import (  # type: ignore
    render_global_css,
    render_sidebar_logo,
    render_sidebar_section,
    render_page_header,
    render_metric_card,
    render_resource_table,
    render_section_header,
    render_empty_state,
)

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ghost Resource Exterminator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_global_css()

# ── Authentication gate ───────────────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    from dashboard.login import render_login_page  # type: ignore
    render_login_page()
    st.stop()

# ── DB init & ensure schema is up to date ────────────────────────────────────
init_db()


# ── Data helpers ──────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    """Load all scan results from the local SQLite database."""
    records = get_all_resources()
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    # Ensure required columns always exist
    for col in ["resource_id", "resource_type", "region", "utilization", "status", "reason", "detected_at"]:
        if col not in df.columns:
            df[col] = "" if col != "utilization" else 0.0
    df["detected_at"] = pd.to_datetime(df["detected_at"], errors="coerce")
    df["utilization"] = pd.to_numeric(df["utilization"], errors="coerce").fillna(0.0)
    return df


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_logo()

    # Identity + logout
    identity = st.session_state.get("aws_identity", "")
    region   = st.session_state.get("aws_default_region", "us-east-1")
    if identity:
        st.markdown(
            f"<div style='font-size:0.7rem;color:#5a5a8a;padding:4px 0 2px;word-break:break-all;'>"
            f"🔐 <b style='color:#6c6c9a;'>{region}</b><br>{identity}</div>",
            unsafe_allow_html=True,
        )
    if st.button("🚪 Logout", use_container_width=True):
        for k in ["authenticated", "aws_access_key_id", "aws_secret_access_key",
                  "aws_default_region", "aws_session_token", "aws_identity"]:
            st.session_state.pop(k, None)
        clear_resources()   # wipe DB on logout for security
        st.rerun()

    render_sidebar_section("Scanner")

    ALL_AWS_REGIONS = [
        "All Regions (default)",
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "ap-south-1", "ap-southeast-1", "ap-southeast-2",
        "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
        "ca-central-1",
        "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-north-1",
        "sa-east-1", "me-south-1", "af-south-1",
    ]

    ALL_RESOURCE_TYPES = [
        "EC2", "EBS", "Snapshot", "EIP", "ELB",
        "SecurityGroup", "AMI", "StoppedEC2", "EFS", "NATGateway"
    ]

    scan_region_choice = st.selectbox(
        "Scan Target Region",
        options=ALL_AWS_REGIONS,
        key="scan_region_picker",
        help="'All Regions' scans your entire AWS account. Pick one region for a faster targeted scan.",
    )

    scan_types_choice = st.multiselect(
        "Resource Types to Scan",
        options=ALL_RESOURCE_TYPES,
        default=ALL_RESOURCE_TYPES,
        help="Deselect types to skip them during the scan.",
    )

    if st.button("🔍 Run Live AWS Scan", use_container_width=True):
        if not scan_types_choice:
            st.error("Please select at least one resource type.")
        else:
            label = scan_region_choice if scan_region_choice != "All Regions (default)" else "all regions"
            with st.spinner(f"Scanning {label} for {len(scan_types_choice)} resource type(s)…"):
                try:
                    from zombie_detector import scan_all  # type: ignore
                    regions_arg = None if scan_region_choice == "All Regions (default)" else [scan_region_choice]
                    scanned_resources = scan_all(
                        clear_before_scan=True,
                        regions=regions_arg,
                        resource_types=scan_types_choice,
                    )
                    st.success(f"✅ Scan complete — {label}")

                    # ── Auto-save scan to S3 history ──────────────────────
                    try:
                        from s3_uploader import save_scan_history_to_s3  # type: ignore
                        _acct = ""
                        _ident = st.session_state.get("aws_identity", "")
                        if "Account:" in _ident:
                            _acct = _ident.split("Account:")[1].strip().split("|")[0].strip()
                        _hist_ok, _hist_uri = save_scan_history_to_s3(
                            resources=scanned_resources,
                            account_id=_acct or "unknown",
                            region=label,
                            scan_types=scan_types_choice,
                            s3_region=st.session_state.get("aws_default_region"),
                        )
                        if _hist_ok:
                            st.caption(f"☁️ History saved → `{_hist_uri}`")
                    except Exception as _hist_err:
                        st.caption(f"⚠️ History save skipped: {_hist_err}")

                    st.rerun()
                except Exception as e:
                    st.error(f"Scan failed: {e}")
                    st.caption("💡 Check your AWS credentials and IAM permissions.")


    render_sidebar_section("Filters")

    # Load raw data for filters
    df_raw = load_data()

    # Dynamic resource types from DB (only show types that exist in data)
    db_types = sorted(df_raw["resource_type"].dropna().unique().tolist()) if not df_raw.empty else []
    type_options = ["All"] + (db_types if db_types else ALL_RESOURCE_TYPES)
    filter_type   = st.selectbox("Resource Type", type_options)
    filter_status = st.selectbox("Status", ["All", "Zombie", "Active"])

    st.markdown("---")
    render_sidebar_section("Legend")
    st.markdown(
        """
        <div style="font-size:0.75rem; color:#5a5a7a; line-height:2.2;">
            🧟 <span style="color:#ff4b4b;">Zombie</span> — idle / unattached / unused<br>
            ✅ <span style="color:#21c55d;">Active</span> — resource in normal use
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown(
        """<div style="font-size:0.68rem; color:#3a3a5a; text-align:center; letter-spacing:0.05em;">
        Ghost Resource Exterminator v2.0<br>Boto3 · CloudWatch · Streamlit
        </div>""",
        unsafe_allow_html=True,
    )


# ── Apply filters ─────────────────────────────────────────────────────────────
last_scan = None
df = df_raw.copy()

if not df.empty:
    last_scan_val = df["detected_at"].dropna().max()
    if pd.notna(last_scan_val):
        last_scan = pd.to_datetime(last_scan_val).strftime("%Y-%m-%d %H:%M") + " UTC"
    if filter_type != "All":
        df = df[df["resource_type"] == filter_type]
    if filter_status != "All":
        df = df[df["status"] == filter_status]


# ── Header ────────────────────────────────────────────────────────────────────
render_page_header(last_scan)


# ── Metric Cards ──────────────────────────────────────────────────────────────
if not df_raw.empty:
    stats = get_summary_stats()
    zombie_pct = round((stats["zombie"] / stats["total"]) * 100) if stats["total"] else 0

    # Configuration for each resource type card
    TYPE_CARD_CONFIGS = {
        "EC2":           ("EC2 Zombies",      "💻", "#ff9f43", "idle instances"),
        "EBS":           ("EBS Zombies",       "💽", "#f1fa8c", "unattached volumes"),
        "Snapshot":      ("Snapshot Zombies",  "📸", "#c56cf0", "old snapshots"),
        "EIP":           ("EIP Zombies",       "🌐", "#ff79c6", "unassociated IPs"),
        "ELB":           ("ELB Zombies",       "⚖️", "#ff5555", "idle load balancers"),
        "SecurityGroup": ("SG Zombies",        "🛡️", "#50fa7b", "unused groups"),
        "AMI":           ("AMI Zombies",       "💾", "#ffb86c", "unused images"),
        "StoppedEC2":    ("Stopped EC2s",      "🛑", "#ff5555", "stopped instances"),
        "EFS":           ("EFS Zombies",       "📁", "#8be9fd", "orphaned EFS"),
        "NATGateway":    ("NATG Zombies",      "🔌", "#f1fa8c", "unused NATs"),
    }

    # Only show type cards where there are zombie findings
    active_type_cards = []
    for rtype, (label, icon, color, subtitle) in TYPE_CARD_CONFIGS.items():
        key = f"{rtype.lower()}_zombie"
        count = stats.get(key, 0)
        if count > 0:
            active_type_cards.append((label, count, icon, color, subtitle))

    all_cards = [
        ("Total Scanned",    stats["total"],  "📦", "#8be9fd", "across all regions"),
        ("Zombie Resources", stats["zombie"], "🧟", "#ff4b4b", f"{zombie_pct}% of total"),
    ] + active_type_cards

    cols_per_row = 5
    for i in range(0, len(all_cards), cols_per_row):
        row_items = all_cards[i:i + cols_per_row]
        cols = st.columns(len(row_items))
        for col, item in zip(cols, row_items):
            with col:
                render_metric_card(item[0], item[1], item[2], item[3], subtitle=item[4])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    render_section_header("Analytics", "Visual breakdown of your scanned resources", "📊")

    chart_left, chart_right = st.columns(2)

    with chart_left:
        status_counts = df_raw["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]

        fig_donut = go.Figure(go.Pie(
            labels=status_counts["Status"],
            values=status_counts["Count"],
            hole=0.62,
            marker={
                "colors": ["#ff4b4b" if s == "Zombie" else "#21c55d" for s in status_counts["Status"]],
                "line": {"color": "#060612", "width": 3},
            },
            textinfo="percent+label",
            textfont={"family": "Inter", "size": 13, "color": "#e2e2f0"},
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
        ))
        fig_donut.add_annotation(
            text=f"<b>{stats['zombie']}</b><br><span style='font-size:10px'>zombies</span>",
            x=0.5, y=0.5, showarrow=False,
            font={"size": 22, "color": "#ff4b4b", "family": "Inter"},
            align="center",
        )
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#9090b0", "family": "Inter"},
            legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#9090b0", "size": 12},
                    "orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.05},
            margin={"t": 10, "b": 10, "l": 10, "r": 10},
            title={"text": "Resource Status Split", "font": {"color": "#7070a0", "size": 13}, "x": 0.5},
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with chart_right:
        type_status = df_raw.groupby(["resource_type", "status"]).size().reset_index(name="count")
        fig_bar = px.bar(
            type_status, x="resource_type", y="count", color="status",
            barmode="group",
            color_discrete_map={"Zombie": "#ff4b4b", "Active": "#21c55d"},
            labels={"resource_type": "", "count": "Count", "status": ""},
            text="count",
        )
        fig_bar.update_traces(
            textposition="outside",
            textfont={"color": "#9090b0", "size": 11},
            marker={"line": {"width": 0}},
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#9090b0", "family": "Inter"},
            xaxis={"gridcolor": "rgba(108,71,255,0.08)", "tickfont": {"color": "#6060a0", "size": 11}},
            yaxis={"gridcolor": "rgba(108,71,255,0.08)", "tickfont": {"color": "#6060a0", "size": 11}, "title": ""},
            legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#9090b0", "size": 11},
                    "orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.12},
            margin={"t": 30, "b": 10, "l": 10, "r": 10},
            bargap=0.25, bargroupgap=0.08,
            title={"text": "Resources by Type & Status", "font": {"color": "#7070a0", "size": 13}, "x": 0.5},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Regional Breakdown ────────────────────────────────────────────────────
    if df_raw["region"].nunique() > 1:
        render_section_header("Regional Breakdown", "Zombie distribution across AWS regions", "🌍")
        region_zombie = (
            df_raw[df_raw["status"] == "Zombie"]
            .groupby("region").size().reset_index(name="Zombie Count")
            .sort_values("Zombie Count", ascending=True)
        )
        if not region_zombie.empty:
            fig_region = go.Figure(go.Bar(
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
                hovertemplate="<b>%{y}</b><br>Zombies: %{x}<extra></extra>",
            ))
            fig_region.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#9090b0", "family": "Inter"},
                xaxis={"gridcolor": "rgba(108,71,255,0.08)", "tickfont": {"color": "#6060a0"}},
                yaxis={"gridcolor": "rgba(0,0,0,0)", "tickfont": {"color": "#8080b0", "size": 11}},
                margin={"t": 10, "b": 10, "l": 10, "r": 30},
                height=max(200, len(region_zombie) * 36),
            )
            st.plotly_chart(fig_region, use_container_width=True)


# ── Resource Inventory Table ──────────────────────────────────────────────────
filtered_count = len(df)
zombie_count   = int((df["status"] == "Zombie").sum()) if not df.empty else 0

render_section_header(
    "Resource Inventory",
    f"{filtered_count} resources · {zombie_count} zombies detected",
    "🗂️",
)

if df_raw.empty:
    render_empty_state()
elif df.empty:
    st.info("ℹ️ No resources match the current filter. Adjust the sidebar filters.")
else:
    render_resource_table(df)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Download Report ──────────────────────────────────────────────────────
    dl_col1, dl_col2, dl_col3 = st.columns([1.2, 1.2, 1.4])
    with dl_col1:
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name="zombie_resources_report.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with dl_col2:
        df_json = df.copy()
        if "detected_at" in df_json.columns:
            df_json["detected_at"] = df_json["detected_at"].astype(str)
        json_data = df_json.to_json(orient="records", indent=2).encode("utf-8")
        st.download_button(
            label="📥 Download JSON",
            data=json_data,
            file_name="zombie_resources_report.json",
            mime="application/json",
            use_container_width=True,
        )
    with dl_col3:
        if st.button("☁️ Upload Report to S3", use_container_width=True, key="s3_upload_btn"):
            from s3_uploader import upload_report_to_s3  # type: ignore
            with st.spinner("Uploading report to s3://chittesh-demo …"):
                ok, result = upload_report_to_s3(
                    df,
                    bucket="chittesh-demo",
                    region=st.session_state.get("aws_default_region"),
                )
            if ok:
                st.success(f"✅ Report uploaded!\n\n`{result}`")
            else:
                st.error(f"❌ Upload failed: {result}")


# ── Cleanup Actions Panel ─────────────────────────────────────────────────────
if not df_raw.empty:
    render_section_header("Cleanup Actions", "Select and eliminate zombie resources", "🗑️")

    st.markdown(
        """
        <div style="
            background: rgba(255,75,75,0.06);
            border: 1px solid rgba(255,75,75,0.18);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 24px;
            font-size: 0.82rem;
            color: #cc6666;
            display: flex; align-items: center; gap: 10px;
        ">
            <span style="font-size:1.1rem;">⚠️</span>
            <span>
                <strong style="color:#ff4b4b;">Danger zone:</strong>
                Deletion/Termination is <strong>permanent and irreversible</strong>.
                Type the Resource ID to confirm before deleting.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    TYPE_DISPLAY = {
        "EC2":           ("💻 EC2 Instances",    "Terminate Instance"),
        "EBS":           ("💽 EBS Volumes",       "Delete Volume"),
        "Snapshot":      ("📸 Snapshots",          "Delete Snapshot"),
        "EIP":           ("🌐 Elastic IPs",        "Release EIP"),
        "ELB":           ("⚖️ Load Balancers",    "Delete Load Balancer"),
        "SecurityGroup": ("🛡️ Security Groups",  "Delete Security Group"),
        "AMI":           ("💾 AMIs",               "Deregister AMI"),
        "StoppedEC2":    ("🛑 Stopped EC2s",       "Terminate Instance"),
        "EFS":           ("📁 EFS Systems",         "Delete EFS"),
        "NATGateway":    ("🔌 NAT Gateways",       "Delete NAT Gateway"),
    }

    import cleanup as _cleanup  # type: ignore

    CLEANUP_FUNCS = {
        "EC2":           _cleanup.terminate_instance,
        "EBS":           _cleanup.delete_ebs_volume,
        "Snapshot":      _cleanup.delete_snapshot,
        "EIP":           _cleanup.release_eip,
        "ELB":           _cleanup.delete_load_balancer,
        "SecurityGroup": _cleanup.delete_security_group,
        "AMI":           _cleanup.deregister_ami,
        "StoppedEC2":    _cleanup.terminate_instance,
        "EFS":           _cleanup.delete_efs,
        "NATGateway":    _cleanup.delete_nat_gateway,
    }

    # Only show tabs for resource types that actually have zombies
    zombie_types = [
        t for t in TYPE_DISPLAY.keys()
        if not df_raw[(df_raw["resource_type"] == t) & (df_raw["status"] == "Zombie")].empty
    ]

    if not zombie_types:
        st.success("✅ No zombie resources found. Your AWS account is clean!")
    else:
        tab_titles = [TYPE_DISPLAY.get(t, (t, "Delete"))[0] for t in zombie_types]
        tab_objects = st.tabs(tab_titles)

        for tab, rtype in zip(tab_objects, zombie_types):
            with tab:
                zombies_df = df_raw[(df_raw["resource_type"] == rtype) & (df_raw["status"] == "Zombie")].copy()

                if zombies_df.empty:
                    st.success(f"✅ No zombie {rtype} resources found.")
                    continue

                # ── Single Resource Cleanup ───────────────────────────────
                t_col1, t_col2 = st.columns([3, 2])
                with t_col1:
                    selected_id = st.selectbox(
                        f"Select Zombie {rtype}",
                        options=zombies_df["resource_id"].tolist(),
                        key=f"sel_{rtype}",
                    )
                    info = zombies_df[zombies_df["resource_id"] == selected_id].iloc[0]

                    util_row = (
                        f"<tr><td style='color:#5a5a7a;padding:3px 0;'>Avg CPU</td>"
                        f"<td style='color:#ff4b4b;'>{info['utilization']:.2f}%</td></tr>"
                        if rtype in ("EC2",) else ""
                    )
                    st.markdown(
                        f'<div style="background:rgba(255,75,75,0.05);border:1px solid rgba(255,75,75,0.15);'
                        f'border-radius:12px;padding:16px 20px;margin-top:8px;">'
                        f'<table style="border-collapse:collapse;width:100%;font-size:0.8rem;">'
                        f'<tr><td style="color:#5a5a7a;padding:4px 0;width:80px;">Resource</td>'
                        f'<td style="color:#e2e2f0;font-family:monospace;">{info["resource_id"]}</td></tr>'
                        f'<tr><td style="color:#5a5a7a;padding:4px 0;">Region</td>'
                        f'<td style="color:#e2e2f0;">{info["region"]}</td></tr>'
                        f'{util_row}'
                        f'<tr><td style="color:#5a5a7a;padding:4px 0;">Reason</td>'
                        f'<td style="color:#9090b0;font-size:0.78rem;">{info["reason"]}</td></tr>'
                        f'</table></div>',
                        unsafe_allow_html=True,
                    )

                with t_col2:
                    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
                    confirm_input = st.text_input(
                        "Type Resource ID to confirm deletion",
                        placeholder=str(selected_id),
                        key=f"confirm_{rtype}",
                    )
                    btn_label = TYPE_DISPLAY.get(rtype, (rtype, "Delete"))[1]
                    if st.button(f"🗑️ {btn_label}", type="primary", use_container_width=True, key=f"btn_{rtype}"):
                        if confirm_input.strip() == str(selected_id):
                            with st.spinner(f"Eliminating {selected_id}…"):
                                fn = CLEANUP_FUNCS.get(rtype)
                                if fn and fn(selected_id, region=str(info["region"]), dry_run=False):
                                    delete_resource(selected_id)
                                    st.success(f"✅ {selected_id} eliminated successfully.")
                                    st.rerun()
                                else:
                                    st.error("❌ Elimination failed. Check IAM permissions.")
                        else:
                            st.error("❌ Resource ID mismatch. Please type exactly as shown.")

                # ── Bulk Auto-Cleaner ─────────────────────────────────────
                st.markdown("---")
                st.markdown(
                    f"<span style='font-size:0.9rem;font-weight:600;color:#ff79c6;'>⚡ Auto-Clean All {rtype} Zombies</span>",
                    unsafe_allow_html=True,
                )
                ac1, ac2 = st.columns([3, 2])
                with ac1:
                    st.markdown(
                        f"<div style='font-size:0.8rem;color:#8080a0;padding-top:4px;'>"
                        f"Automatically delete all <b style='color:#ff4b4b;'>{len(zombies_df)}</b> "
                        f"zombie {rtype} resource(s). This is irreversible.</div>",
                        unsafe_allow_html=True,
                    )
                    auto_confirm = st.checkbox(
                        f"I understand — permanently delete all {len(zombies_df)} zombie {rtype}(s)",
                        key=f"auto_chk_{rtype}",
                    )
                with ac2:
                    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
                    if st.button(
                        f"⚡ Auto-Clean All ({len(zombies_df)})",
                        type="primary",
                        use_container_width=True,
                        key=f"auto_btn_{rtype}",
                        disabled=not auto_confirm,
                    ):
                        progress = st.progress(0)
                        success_n, fail_n = 0, 0
                        fn = CLEANUP_FUNCS.get(rtype)
                        total = len(zombies_df)
                        if fn:
                            for idx, row in enumerate(zombies_df.itertuples()):
                                with st.spinner(f"Deleting {row.resource_id}…"):
                                    ok = fn(row.resource_id, region=str(row.region), dry_run=False)
                                    if ok:
                                        delete_resource(row.resource_id)
                                        success_n += 1
                                    else:
                                        fail_n += 1
                                progress.progress((idx + 1) / total)
                        if success_n:
                            st.success(f"✅ {success_n} {rtype}(s) cleaned up!")
                        if fail_n:
                            st.error(f"❌ {fail_n} failed. Check IAM permissions.")
                        st.rerun()



# ── Report Generator ──────────────────────────────────────────────────────────
if not df_raw.empty:
    render_section_header(
        "Report Generator",
        "Generate a rich HTML report and upload it to S3",
        "📋",
    )

    st.markdown(
        """
        <div style="
            background: rgba(108,71,255,0.06);
            border: 1px solid rgba(108,71,255,0.18);
            border-radius: 14px;
            padding: 16px 22px;
            margin-bottom: 20px;
            font-size: 0.82rem;
            color: #8080b0;
            line-height: 1.7;
        ">
            <span style="font-size:1rem;">📋</span>
            &nbsp; Generates a <strong style="color:#c4b5fd;">self-contained HTML report</strong>
            with embedded charts, summary cards, resource table and cost-savings estimate.
            Both <code style="color:#8be9fd;">zombie_report.html</code> and
            <code style="color:#8be9fd;">zombie_report.csv</code> are uploaded to
            <code style="color:#ff9f43;">s3://chittesh-demo/reports/&lt;account_id&gt;/&lt;timestamp&gt;/</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Report options ────────────────────────────────────────────────────────
    rg_col1, rg_col2 = st.columns(2)
    with rg_col1:
        rg_zombies_only = st.checkbox(
            "🧟 Zombies only in resource table",
            value=True,
            key="rg_zombies_only",
            help="Include only zombie resources in the report table (recommended).",
        )
    with rg_col2:
        rg_include_charts = st.checkbox(
            "📊 Embed charts in report",
            value=True,
            key="rg_include_charts",
            help="Embed Plotly charts as images. Disable for a faster, lighter report.",
        )

    st.markdown("<br/>", unsafe_allow_html=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    btn_col1, btn_col2, btn_col3 = st.columns([1.6, 1.4, 2])

    with btn_col1:
        generate_s3 = st.button(
            "🚀 Generate & Upload to S3",
            use_container_width=True,
            key="rg_generate_s3",
            type="primary",
        )

    with btn_col2:
        generate_local = st.button(
            "📥 Download HTML Report",
            use_container_width=True,
            key="rg_generate_local",
        )

    # ── S3 upload flow ────────────────────────────────────────────────────────
    if generate_s3:
        from report_generator import generate_report_bundle  # type: ignore
        from s3_uploader import upload_report_bundle_to_s3   # type: ignore

        account_id  = ""
        identity    = st.session_state.get("aws_identity", "")
        if "Account:" in identity:
            account_id = identity.split("Account:")[1].strip().split("|")[0].strip()

        region_label = st.session_state.get("aws_default_region", "multi-region")

        with st.spinner("⚙️ Generating report…"):
            bundle = generate_report_bundle(
                df=df_raw,
                stats=get_summary_stats(),
                account_id=account_id or "unknown",
                region=region_label,
                zombies_only=rg_zombies_only,
                include_charts=rg_include_charts,
            )

        with st.spinner("☁️ Uploading to S3…"):
            ok, result = upload_report_bundle_to_s3(
                bundle=bundle,
                bucket="chittesh-demo",
                region=st.session_state.get("aws_default_region"),
            )

        if ok:
            html_uri = result.get("html_uri", "")
            csv_uri  = result.get("csv_uri",  "")
            st.success("✅ Report uploaded to S3 successfully!")
            st.markdown(
                f"""
                <div style="
                    background: rgba(33,197,93,0.06);
                    border: 1px solid rgba(33,197,93,0.2);
                    border-radius: 12px;
                    padding: 16px 20px;
                    margin-top: 8px;
                    font-size: 0.82rem;
                ">
                    <div style="margin-bottom:8px; color:#4a4a7a; font-size:0.72rem;
                                font-weight:700; letter-spacing:0.08em; text-transform:uppercase;">
                        📁 Uploaded Files
                    </div>
                    <div style="margin-bottom:6px;">
                        <span style="color:#5a5a7a;">HTML Report &nbsp;</span>
                        <code style="color:#8be9fd; font-size:0.78rem;">{html_uri}</code>
                    </div>
                    <div>
                        <span style="color:#5a5a7a;">CSV Data &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
                        <code style="color:#8be9fd; font-size:0.78rem;">{csv_uri}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")

    # ── Local HTML download flow ──────────────────────────────────────────────
    if generate_local:
        from report_generator import generate_report_bundle  # type: ignore

        account_id  = ""
        identity    = st.session_state.get("aws_identity", "")
        if "Account:" in identity:
            account_id = identity.split("Account:")[1].strip().split("|")[0].strip()

        region_label = st.session_state.get("aws_default_region", "multi-region")

        with st.spinner("⚙️ Generating report…"):
            bundle = generate_report_bundle(
                df=df_raw,
                stats=get_summary_stats(),
                account_id=account_id or "unknown",
                region=region_label,
                zombies_only=rg_zombies_only,
                include_charts=rg_include_charts,
            )

        filename = f"{bundle['filename_prefix']}_zombie_report.html"
        st.download_button(
            label="📄 Click to download HTML Report",
            data=bundle["html"],
            file_name=filename,
            mime="text/html",
            use_container_width=False,
            key="rg_html_download_btn",
        )
        st.caption(f"📁 File: `{filename}`")



# ── Scan History ──────────────────────────────────────────────────────────────
render_section_header("Scan History", "Browse and reload past scans stored in S3", "🕐")

st.markdown(
    """
    <div style="
        background: rgba(139,233,253,0.05);
        border: 1px solid rgba(139,233,253,0.18);
        border-radius: 14px;
        padding: 14px 20px;
        margin-bottom: 18px;
        font-size: 0.82rem;
        color: #8080b0;
        line-height: 1.7;
    ">
        <span style="font-size:1rem;">🕐</span>
        &nbsp; Every scan is <strong style="color:#c4b5fd;">automatically saved</strong>
        to <code style="color:#ff9f43;">s3://chittesh-demo/history/&lt;account_id&gt;/&lt;timestamp&gt;/</code>.
        Select any past scan below to reload it into the dashboard.
    </div>
    """,
    unsafe_allow_html=True,
)

# Resolve account id for history queries
_hist_account = ""
_hist_ident   = st.session_state.get("aws_identity", "")
if "Account:" in _hist_ident:
    _hist_account = _hist_ident.split("Account:")[1].strip().split("|")[0].strip()

_h_col1, _ = st.columns([1, 5])
with _h_col1:
    if st.button("🔄 Refresh History", use_container_width=True, key="hist_refresh"):
        st.session_state.pop("_hist_entries", None)
        st.session_state.pop("_hist_loaded",  None)
        st.rerun()

# Load + cache the history list (refreshed on demand)
if "_hist_entries" not in st.session_state:
    with st.spinner("Loading scan history from S3…"):
        try:
            from s3_uploader import list_scan_history  # type: ignore
            _h_ok, _h_list = list_scan_history(
                account_id=_hist_account or "unknown",
                s3_region=st.session_state.get("aws_default_region"),
            )
            st.session_state["_hist_entries"] = _h_list if _h_ok else []
        except Exception as _he:
            st.session_state["_hist_entries"] = []
            st.warning(f"Could not load history: {_he}")

_hist_entries: list = st.session_state.get("_hist_entries", [])

if not _hist_entries:
    st.markdown(
        """
        <div style="text-align:center;padding:40px 20px;
                    background:rgba(255,255,255,0.015);border-radius:16px;
                    border:1px dashed rgba(108,71,255,0.18);">
            <div style="font-size:2.5rem;margin-bottom:12px;">🕐</div>
            <div style="color:#4a4a6a;font-size:0.88rem;line-height:1.7;">
                No scan history yet.<br/>
                Run a scan to automatically create your first snapshot in S3.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # ── "Viewing historical scan" banner ─────────────────────────────────────
    if st.session_state.get("_hist_loaded"):
        _lm = st.session_state["_hist_loaded"]
        st.info(
            f"📂 **Viewing historical scan** — "
            f"`{_lm.get('timestamp','?').replace('_',' ')}` · "
            f"{_lm.get('region','?')} · "
            f"{_lm.get('total',0)} resources · "
            f"{_lm.get('zombie',0)} zombies.  "
            f"*(Click 🔍 Run Live AWS Scan to return to live data.)*"
        )
        if st.button("✖ Clear historical view", key="hist_dismiss"):
            st.session_state.pop("_hist_loaded", None)
            st.rerun()

    # ── History table ─────────────────────────────────────────────────────────
    import pandas as _hpd
    _hist_rows = []
    for _e in _hist_entries:
        _ts = _e.get("timestamp", "—").replace("_", " ")
        _types_str = ", ".join(_e.get("scan_types", [])) or "All"
        _hist_rows.append({
            "📅 Timestamp (UTC)": _ts,
            "🌍 Region":          _e.get("region", "—"),
            "🔍 Types Scanned":   _types_str,
            "📦 Total":           _e.get("total", 0),
            "🧟 Zombies":         _e.get("zombie", 0),
            "✅ Active":          _e.get("active", 0),
        })

    _hist_df = _hpd.DataFrame(_hist_rows)
    st.dataframe(
        _hist_df,
        use_container_width=True,
        hide_index=True,
        height=min(420, 44 + len(_hist_df) * 36),
    )

    # ── Entry selector + actions ──────────────────────────────────────────────
    st.markdown("<br/>", unsafe_allow_html=True)
    render_section_header("Snapshot Actions", "Load or delete a specific scan snapshot", "⚙️")

    _entry_labels = [
        f"{_e.get('timestamp','?').replace('_',' ')}  ·  "
        f"{_e.get('region','?')}  ·  "
        f"{_e.get('zombie',0)} zombies / {_e.get('total',0)} total"
        for _e in _hist_entries
    ]

    _sel_label = st.selectbox(
        "Select snapshot",
        options=_entry_labels,
        key="hist_sel",
        label_visibility="collapsed",
    )
    _sel_idx   = _entry_labels.index(_sel_label) if _sel_label in _entry_labels else 0
    _sel_entry = _hist_entries[_sel_idx]

    ha1, ha2, ha3 = st.columns([1.3, 1.2, 3])

    with ha1:
        if st.button("📂 Load into Dashboard", use_container_width=True, key="hist_load"):
            with st.spinner("Loading historical scan from S3…"):
                try:
                    from s3_uploader import load_scan_history_entry  # type: ignore
                    _lok, _lresources = load_scan_history_entry(
                        folder_prefix=_sel_entry["folder_prefix"],
                        s3_region=st.session_state.get("aws_default_region"),
                    )
                    if _lok:
                        # Restore resources into DB (even if the list is empty — valid snapshot)
                        from db import clear_resources, save_resource  # type: ignore
                        clear_resources()
                        for _r in _lresources:
                            try:
                                save_resource(
                                    resource_id  = str(_r.get("resource_id",   "")),
                                    resource_type= str(_r.get("resource_type", "")),
                                    region       = str(_r.get("region",        "")),
                                    utilization  = float(_r.get("utilization", 0)),
                                    status       = str(_r.get("status",  "Unknown")),
                                    reason       = str(_r.get("reason",        "")),
                                )
                            except Exception:
                                pass
                        st.session_state["_hist_loaded"] = _sel_entry
                        if _lresources:
                            st.success(
                                f"✅ Loaded `{_sel_entry.get('timestamp','?').replace('_',' ')}` "
                                f"— {len(_lresources)} resources restored to dashboard."
                            )
                        else:
                            st.info(
                                f"ℹ️ Snapshot `{_sel_entry.get('timestamp','?').replace('_',' ')}` "
                                f"loaded — scan had 0 resources (nothing found in that scan)."
                            )
                        st.rerun()
                    else:
                        st.error("❌ Could not retrieve that snapshot from S3. Check IAM permissions (s3:GetObject).")
                except Exception as _le:
                    st.error(f"❌ Load error: {_le}")


    with ha2:
        if st.button("🗑️ Delete Entry", use_container_width=True, key="hist_del"):
            with st.spinner("Deleting from S3…"):
                try:
                    from s3_uploader import delete_scan_history_entry  # type: ignore
                    _dok, _dmsg = delete_scan_history_entry(
                        folder_prefix=_sel_entry["folder_prefix"],
                        s3_region=st.session_state.get("aws_default_region"),
                    )
                    if _dok:
                        st.success(f"✅ {_dmsg}")
                        st.session_state.pop("_hist_entries", None)
                        st.rerun()
                    else:
                        st.error(f"❌ Delete failed: {_dmsg}")
                except Exception as _de:
                    st.error(f"❌ {_de}")


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")


st.markdown(
    """
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:8px 0 20px;flex-wrap:wrap;gap:8px;">
        <div style="font-size:0.75rem;color:#3a3a5a;">
            🎯 <strong style="color:#6c47ff;">Ghost Resource Exterminator</strong>
            &nbsp;·&nbsp; Python · Boto3 · CloudWatch · Streamlit
        </div>
        <div style="font-size:0.72rem;color:#3a3a5a;letter-spacing:0.05em;">
            💰 Reduce cloud waste &nbsp;·&nbsp; 🌍 Multi-region &nbsp;·&nbsp; 🔒 Secure by default
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
