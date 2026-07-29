# 🎯 Ghost Resource Exterminator

> **A Cloud FinOps tool that hunts down zombie AWS resources eating your budget.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![AWS](https://img.shields.io/badge/AWS-Boto3-orange.svg)](https://boto3.amazonaws.com)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red.svg)](https://streamlit.io)

---

## 🏗️ Architecture

```
AWS Account
    │
    ├─► EC2 Instances ──────► CloudWatch CPU Metrics ──► Zombie if avg CPU < 1%
    ├─► EBS Volumes ─────────────────────────────────► Zombie if unattached
    └─► EBS Snapshots ───────────────────────────────► Zombie if older > 30 days
                                      │
                                    SQLite DB
                                      │
                               Streamlit Dashboard ──► Terminate Button (EC2)
                                      │
                               Cron Scheduler (daily)
```

---

## 📁 Project Structure

```
ghost-resource-exterminator/
├── config.py               # AWS credentials & thresholds
├── db.py                   # SQLite database layer
├── zombie_detector.py      # Main orchestrator (runs all scanners)
├── cleanup.py              # EC2/EBS/Snapshot termination
├── run_scan.py             # CLI entry point
├── scheduler.py            # Automated cron-like scheduling
├── scanner/
│   ├── __init__.py
│   ├── ec2_scanner.py      # EC2 + CloudWatch CPU check
│   ├── ebs_scanner.py      # Unattached EBS volumes
│   └── snapshot_scanner.py # Old EBS snapshots
├── dashboard/
│   ├── app.py              # Streamlit web UI
│   └── components.py       # Reusable UI widgets
├── data/
│   └── zombie_resources.db # SQLite DB (auto-created)
├── requirements.txt
├── .env.example
├── cron_setup.sh
└── README.md
```

---

## ⚙️ Step 1 — AWS Credentials Setup

### Option A: IAM Access Keys (Recommended for local dev)

1. Log in to **AWS Console** → **IAM** → **Users** → **Create User**
2. Attach the following **managed policies**:
   - `AmazonEC2ReadOnlyAccess`
   - `CloudWatchReadOnlyAccess`
   - For cleanup: `AmazonEC2FullAccess` *(only in dev — never production!)*
3. Go to **Security credentials** → **Create access key** → Download CSV

4. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env     # Windows
   cp .env.example .env       # Linux/macOS
   ```

5. Edit `.env` with your credentials:
   ```ini
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   AWS_DEFAULT_REGION=us-east-1
   ```

### Option B: AWS CLI Profile (Alternative)

```bash
aws configure
```
Leave `.env` empty — boto3 auto-uses `~/.aws/credentials`.

> 🔒 **Security Note**: Never commit `.env` to git. Add it to `.gitignore`.

---

## 📦 Step 2 — Installation

```bash
cd "c:\chittesh aws\cloud\ghost-resource-exterminator"
pip install -r requirements.txt
```

---

## 🚀 Step 3 — Running the Scanner

### Demo Mode (no AWS credentials needed)
```bash
python run_scan.py --seed
```

### Live AWS Scan
```bash
python run_scan.py
```

### Scan + Dry-Run Cleanup Report
```bash
python run_scan.py --cleanup
```

### Expected Terminal Output
```
 ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
 ...GHOST Resource Exterminator...

✅ Config valid | Region: us-east-1
✅ DB initialised

🔍 Scanning EC2 instances...
  🧟 i-0a1b2c3d00001 | CPU: 0.12% | Zombie
  ✅ i-0a1b2c3d00004 | CPU: 45.70% | Active

🔍 Scanning EBS volumes...
  🧟 vol-0abc001 | 100GiB gp3 | Unattached | Zombie

🔍 Scanning EBS snapshots...
  🧟 snap-0def001 | 95 days old | Zombie

════════════════════════════════════════════════════════════
  📊 SCAN SUMMARY REPORT
════════════════════════════════════════════════════════════
  Total resources scanned : 7
  🧟 Zombie resources     : 5
  ✅ Active resources     : 2
```

---

## 🖥️ Step 4 — Launch Streamlit Dashboard

```bash
streamlit run dashboard/app.py
```

Opens at: **http://localhost:8501**

### Dashboard Features
| Feature | Description |
|---------|-------------|
| 📦 Metric Cards | Total, Zombie, Active counts by resource type |
| 🥧 Pie Chart | Zombie vs Active distribution |
| 📊 Bar Chart | Zombie count by resource type |
| 🗂️ Resource Table | Filterable by type, status; colour-coded badges |
| 🗑️ Terminate Panel | Select EC2 zombie → type ID to confirm → terminate |
| 🌱 Demo Data | One-click demo load (no AWS needed) |
| 🔍 Live Scan | Trigger real AWS scan from sidebar |

---

## ⏰ Step 5 — Automate with Scheduler

### Option A: Python Scheduler (cross-platform)
```bash
# Run daily at 8AM
python scheduler.py

# Run every 6 hours
python scheduler.py --interval 6
```

### Option B: Linux/macOS Cron Job
```bash
chmod +x cron_setup.sh
./cron_setup.sh
```

### Option C: Windows Task Scheduler (PowerShell as Admin)
```powershell
$action  = New-ScheduledTaskAction -Execute "python" `
           -Argument "C:\chittesh aws\cloud\ghost-resource-exterminator\run_scan.py"
$trigger = New-ScheduledTaskTrigger -Daily -At 8am
Register-ScheduledTask -Action $action -Trigger $trigger `
                       -TaskName "GhostResourceExterminator"
```

---

## 🔐 Security Best Practices

| Practice | Implementation |
|----------|----------------|
| No hardcoded credentials | All keys loaded from `.env` via `python-dotenv` |
| Least-privilege IAM | Use ReadOnly policies for scanning |
| Confirmation before delete | Terminate requires typing resource ID |
| Dry-run by default | `cleanup.py` defaults to `dry_run=True` |
| Gitignore `.env` | Add `.env` to your `.gitignore` |
| Temporary credentials | Supports `AWS_SESSION_TOKEN` for STS/MFA |

---

## 💰 Expected Cost Savings

| Resource | Est. Monthly Waste |
|----------|--------------------|
| Idle t3.medium EC2 | ~$30/month |
| 100 GiB unattached gp3 EBS | ~$10/month |
| 1 TB old snapshots | ~$25/month |
| **10 zombie EC2 + 20 EBS + 50 snaps** | **~$800-2000+/month** |

---

## 🛠️ Zombie Detection Rules

| Resource | Rule | Threshold |
|----------|------|-----------|
| EC2 Instance | Avg CPUUtilization (CloudWatch, 7 days) | < 1% |
| EBS Volume | Volume state | `available` (unattached) |
| EBS Snapshot | Age since creation | > 30 days |

All thresholds are configurable via `.env`.

---

## 📄 License

MIT — Free to use. Built for learning and real-world FinOps practice.
