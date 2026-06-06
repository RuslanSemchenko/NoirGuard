FROM python:3.14-slim

# Install system dependencies and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    git \
    && npm install -g snyk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up environment for the audit tools
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pylint pytest pytest-asyncio

# Set a non-root user for security
RUN useradd -m auditor
USER auditor
