# Matches requires-python in pyproject.toml.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv==0.12.23

# Dependencies first, so editing the source does not invalidate this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src

ENV MCP_HOST="0.0.0.0"
ENV MCP_PORT=8000
EXPOSE 8000

# --no-sync: run what was installed above, without pulling the dev group in.
CMD ["uv", "run", "--no-sync", "src/main.py"]
