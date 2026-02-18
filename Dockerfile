FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && \
    rm -rf /var/lib/apt/lists/*

# Install marksync from local source
COPY pyproject.toml README.md VERSION ./
COPY marksync/ marksync/
RUN pip install --no-cache-dir ".[all]"

# Install markpact separately (for deployment agent)
RUN pip install --no-cache-dir markpact

# Shared project directory
RUN mkdir -p /project
WORKDIR /project

# Default: run as server
ENTRYPOINT ["marksync"]
CMD ["server", "README.md", "--port", "8765"]
