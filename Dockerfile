# Multi-stage build for smaller final image
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 dnstest && \
    mkdir -p /app/logs && \
    chown -R dnstest:dnstest /app

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/dnstest/.local

# Make sure scripts in .local are usable
ENV PATH=/home/dnstest/.local/bin:$PATH

# Copy application code
COPY --chown=dnstest:dnstest app/ ./app/

# Copy example config as default config
COPY --chown=dnstest:dnstest config.yaml.example ./config.yaml

# Switch to non-root user
USER dnstest

# Expose port
EXPOSE 8900

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8900/health').read()"

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8900"]
