# Use a Python base image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the contents of the repository to the working directory
COPY . .

# Install the project dependencies
RUN pip install uv
RUN uv sync

ENV MCP_HOST="0.0.0.0"
ENV MCP_PORT=8000

# Command to run the server
CMD ["uv", "run", "src/main.py"]
