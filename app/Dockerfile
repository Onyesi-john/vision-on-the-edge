# Use a minimal and stable Python base image
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (for OpenCV + curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application codes
COPY . .

# Expose Flask app port
EXPOSE 5000

# Healthcheck for Docker to monitor the container
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:5000/video_feed || exit 1

# Start the Flask app
CMD ["python", "app.py"]
