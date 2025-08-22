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

# Copy the application code
COPY . .

# Expose Flask app port
EXPOSE 5000

# Healthcheck: lightweight endpoint that doesn't touch the camera
#HEALTHCHECK --interval=5s --timeout=3s --start-period=5s \
#  CMD curl -f http://localhost:5000/health || exit 1

# Start the Flask app
CMD ["python", "app.py"]
