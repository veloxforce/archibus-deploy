FROM python:3.11-slim

WORKDIR /app

# Install uv for dependency management
COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --no-dev

# Copy application code
COPY server.py ./
COPY fastmcp.json ./
COPY src/ ./src/

# Expose HTTP port
EXPOSE 8000

# Run FastMCP server with HTTP transport
CMD ["uv", "run", "python", "server.py"]
