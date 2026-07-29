# ---- Ghost Resource Exterminator — Dockerfile ----
# Base image: slim Python, small footprint for a t2/t3.micro EC2 instance
FROM python:3.11-slim

# Don't buffer stdout/stderr (so `docker logs` shows output immediately)
ENV PYTHONUNBUFFERED=1

# Set working directory inside the container
WORKDIR /app

# Copy only requirements first -> Docker caches this layer so rebuilds
# are fast when you only change app code, not dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY . .

# Make sure the SQLite data folder exists (db.py writes here)
RUN mkdir -p /app/data

# Streamlit's default port
EXPOSE 8501

# Basic container health check — Streamlit exposes a health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Run the dashboard. --server.address=0.0.0.0 is required so the app is
# reachable from outside the container, not just localhost inside it.
CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]

