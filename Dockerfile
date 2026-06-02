FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Whisper model
RUN python -c "import whisper; whisper.load_model('base')"

# Copy application
COPY . .

EXPOSE 8000

# Production command with Gunicorn + Uvicorn workers
CMD gunicorn main:sio_app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --keep-alive 5
