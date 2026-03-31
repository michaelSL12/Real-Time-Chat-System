# Base Python image for the backend application.
FROM python:3.10-slim

# Set the working directory inside the container.
WORKDIR /app

# Python runtime settings:
# - disable .pyc generation
# - force stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for building Python packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better Docker layer caching.
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the project source code into the container.
COPY . .

# Expose the backend port.
EXPOSE 8000

# Run database migrations and then start the FastAPI application.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]