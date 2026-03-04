# Runtime stage
# Use NVIDIA CUDA runtime as base for GPU support
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runner

WORKDIR /app

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 and runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libmagic1 \
    libmagic-dev \
    file \
    ca-certificates \
    curl \
    build-essential \
    python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a symbolic link for python
RUN ln -s /usr/bin/python3.11 /usr/bin/python

# Create a virtual environment in the runner stage directly
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install python dependencies in the runner stage to ensure compatibility
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /app/temp_files \
    && chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV TEMP_DIR="/app/temp_files"
ENV GRADIO_TEMP_DIR="/app/temp_files"
# Ensure GPU is used if available
ENV COMPUTE_DEVICE="CUDA"

# Use the non-root user
USER appuser

# Gradio default port
EXPOSE 7860

# Launch the app
CMD ["python", "app.py"]
