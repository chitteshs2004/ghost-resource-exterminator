"""
dashboard/login.py
==================
Premium AWS IAM login page for Ghost Resource Exterminator.

Credentials entered here are stored only in st.session_state for the
duration of the browser session — never written to disk.
"""

from __future__ import annotations
import streamlit as st  # type: ignore


_AWS_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "ap-south-1", "ap-southeast-1", "ap-southeast-2",
    "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
    "ca-central-1",
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-north-1",
    "sa-east-1", "me-south-1", "af-south-1",
]


def _inject_login_css() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    html, body, [data-testid="stApp"], .stApp, div[data-testid="stAppViewContainer"] {
        background: #020205 !important;
        background-color: #020205 !important;
        font-family: 'Inter', sans-serif !important;
        overflow: hidden;
        color: #ffffff !important;
    }

    /* Animated background */
    [data-testid="stApp"]::before {
        content: "";
        position: fixed;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle at 50% 50%, rgba(108,71,255,0.08) 0%, transparent 25%),
                    radial-gradient(circle at 20% 80%, rgba(157,78,221,0.05) 0%, transparent 20%),
                    radial-gradient(circle at 80% 20%, rgba(108,71,255,0.05) 0%, transparent 20%);
        animation: rotate 60s linear infinite;
        z-index: -1;
    }

    @keyframes rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stMainBlockContainer"] { 
        padding-top: 5vh !important; 
        max-width: 100% !important;
        background: transparent !important;
    }
    
    div[data-testid="stForm"] {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 28px !important;
        padding: 40px !important;
        margin-bottom: 30px !important;
        box-shadow: 0 40px 100px rgba(0,0,0,0.6), inset 0 1px 1px rgba(255,255,255,0.1) !important;
        backdrop-filter: blur(20px) !important;
    }

    /* Input fields */
    [data-testid="stTextInput"] input {
        background: transparent !important;
        border: none !important;
        color: #fff !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        padding: 12px 16px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* Input Container (wraps input + eye icon) */
    [data-testid="stTextInput"] div[data-baseweb="input"] {
        background: rgba(255,255,255,0.03) !important;
        background-color: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(5px);
        transition: all 0.3s ease !important;
        overflow: hidden !important;
    }
    
    [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: rgba(108,71,255,0.5) !important;
        box-shadow: 0 0 0 4px rgba(108,71,255,0.15), 0 8px 16px rgba(0,0,0,0.2) !important;
        background: rgba(255,255,255,0.05) !important;
        background-color: rgba(255,255,255,0.05) !important;
    }
    
    [data-testid="stTextInput"] input:focus {
        box-shadow: none !important;
        outline: none !important;
    }

    [data-testid="stTextInput"] label {
        color: rgba(255,255,255,0.5) !important;
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        margin-bottom: 8px !important;
    }
    
    /* Password visibility toggle button & container fix */
    [data-testid="stTextInput"] > div > div, 
    [data-testid="stTextInput"] > div > div > div {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    /* Hide the "Press Enter to submit" text hint in text inputs */
    [data-testid="InputInstructions"] {
        display: none !important;
    }

    /* Password eye button styling */
    [data-testid="stTextInput"] button[kind="secondaryFormSubmit"],
    [data-testid="stTextInput"] button[kind="secondary"],
    [data-testid="stTextInput"] button {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
    }
    [data-testid="stTextInput"] button:hover,
    [data-testid="stTextInput"] button:active,
    [data-testid="stTextInput"] button:focus {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    /* Ensure the button wrapper div has no background */
    [data-testid="stTextInput"] [data-baseweb="input"] > div:last-child {
        background: transparent !important;
        background-color: transparent !important;
        margin-right: -4px !important;
    }
    
    [data-testid="stTextInput"] button, [data-testid="stTextInput"] svg {
        color: #6c47ff !important;
        fill: #6c47ff !important;
    }

    /* Selectbox */
    [data-testid="stSelectbox"] > div > div {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        color: #fff !important;
        backdrop-filter: blur(5px);
        transition: all 0.3s ease !important;
    }
    [data-testid="stSelectbox"] > div > div:hover {
        border-color: rgba(255,255,255,0.2) !important;
    }
    [data-testid="stSelectbox"] label {
        color: rgba(255,255,255,0.5) !important;
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
    }

    /* Submit button */
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #6c47ff 0%, #9d4edd 100%) !important;
        border: none !important;
        border-radius: 14px !important;
        color: #fff !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 1rem !important;
        font-weight: 800 !important;
        height: 54px !important;
        letter-spacing: 0.03em !important;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        width: 100% !important;
        box-shadow: 0 10px 30px rgba(108,71,255,0.3) !important;
        margin-top: 10px !important;
    }
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
        transform: translateY(-3px) scale(1.01) !important;
        box-shadow: 0 20px 40px rgba(108,71,255,0.5) !important;
        filter: brightness(1.1) !important;
    }
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:active {
        transform: translateY(0) scale(0.98) !important;
    }

    /* Alert / error */
    [data-testid="stAlert"] {
        background: rgba(255, 75, 75, 0.05) !important;
        border: 1px solid rgba(255, 75, 75, 0.2) !important;
        border-radius: 15px !important;
        backdrop-filter: blur(10px);
        font-size: 0.88rem !important;
        padding: 1rem !important;
    }

    /* Hide Streamlit branding */
    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)



def _validate_credentials(access_key: str, secret_key: str, region: str) -> tuple[bool, str]:
    """
    Calls STS GetCallerIdentity to validate the given credentials.
    Returns (success: bool, message: str).
    """
    import boto3  # type: ignore
    import botocore.exceptions  # type: ignore

    kwargs: dict = {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "region_name": region,
    }

    try:
        sts = boto3.client("sts", **kwargs)
        identity = sts.get_caller_identity()
        account_id = identity.get("Account", "unknown")
        arn = identity.get("Arn", "unknown")
        return True, f"Account: {account_id} | {arn}"
    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("InvalidClientTokenId", "SignatureDoesNotMatch", "AuthFailure"):
            return False, "❌ Invalid credentials — check your Access Key ID and Secret Key."
        return False, f"❌ AWS error: {e.response['Error']['Message']}"
    except botocore.exceptions.NoCredentialsError:
        return False, "❌ No credentials provided."
    except Exception as e:
        return False, f"❌ Connection error: {str(e)}"


def render_login_page() -> None:
    """
    Renders the full-screen premium login page.
    On successful auth, sets st.session_state['authenticated'] = True
    and stores credentials in session_state.
    """
    _inject_login_css()

    # ── Centered card layout ────────────────────────────────────────────────
    _, col, _ = st.columns([1, 1.6, 1])

    with col:
        # Hero branding
        st.markdown("""
        <div style="text-align:center; padding: 60px 0 40px;">
            <div style="margin-bottom: 24px;">
                <img src="data:image/png;base64,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" style="height:90px; border-radius: 12px; filter:drop-shadow(0 0 15px rgba(255,153,0,0.5));" />
            </div>
            <div style="
                font-size:2.5rem; font-weight:900; letter-spacing:-0.04em; line-height:1.1;
                background:linear-gradient(135deg,#ffffff 0%,#ff9900 50%,#ffb84d 100%);
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                margin-bottom:12px;">
                Ghost Resource<br>Exterminator
            </div>
            <div style="
                display: inline-block;
                padding: 4px 12px;
                background: rgba(108,71,255,0.1);
                border: 1px solid rgba(108,71,255,0.2);
                border-radius: 100px;
                font-size:0.75rem; color:#8b5cf6; font-weight:700; letter-spacing:0.05em;
                text-transform: uppercase;
            ">
                Enterprise Cloud FinOps · v2.0
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Login form layout
        with st.form("aws_login_form", clear_on_submit=False):
            st.markdown("""
            <div style="font-size:1.1rem; font-weight:700; color:#ffffff; margin-bottom:8px; display:flex; align-items:center; gap:10px;">
                <span style="opacity:0.8;">🔐</span> &nbsp;AWS Account Access
            </div>
            <div style="font-size:0.85rem; color:rgba(255,255,255,0.4); margin-bottom:32px; line-height:1.5;">
                Enter your IAM credentials to begin the scanning process. Your keys are never stored on disk.
            </div>
            """, unsafe_allow_html=True)
            access_key = st.text_input(
                "Access Key ID",
                placeholder="AKIAIOSFODNN7EXAMPLE",
                help="Your IAM user Access Key ID (starts with AKIA...)",
            )
            secret_key = st.text_input(
                "Secret Access Key",
                placeholder="••••••••••••••••••••••••••••••••••••••••",
                type="password",
                help="Your IAM user Secret Access Key",
            )
            region = "us-east-1"  # Default region hardcoded to hide selectbox

            submitted = st.form_submit_button("Connect to AWS →", use_container_width=True)

        # Handle submission
        if submitted:
            # If the user left both blank, they are likely trying to use IAM roles/local config
            if (not access_key and secret_key) or (access_key and not secret_key):
                st.error("Please enter both Access Key ID and Secret Access Key, or leave both blank to use an IAM Role.")
            else:
                with st.spinner("Validating credentials with AWS STS…"):
                    ok, msg = _validate_credentials(access_key, secret_key, region)

                if ok:
                    # Store in session_state — never on disk
                    st.session_state["authenticated"] = True
                    st.session_state["aws_access_key_id"] = access_key
                    st.session_state["aws_secret_access_key"] = secret_key
                    st.session_state["aws_default_region"] = region
                    st.session_state["aws_identity"] = msg
                    
                    # Clear the database for the new user session
                    from db import clear_resources  # type: ignore
                    clear_resources()
                    
                    st.success(f"✅ Connected! {msg}")
                    st.rerun()
                else:
                    st.error(msg)

        # Security note
        st.markdown("""
        <div style="text-align:center; margin-top:8px;">
            <div style="font-size:0.72rem; color:#3a3a5a; line-height:1.6;">
                🔒 Credentials only exist in your browser session memory.<br>
                Use a read-only IAM policy for maximum security.
            </div>
        </div>
        """, unsafe_allow_html=True)
