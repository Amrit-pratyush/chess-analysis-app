# Use a lightweight official Python Linux image
FROM python:3.11-slim

# Install Stockfish and essential system utilities
RUN apt-get update && apt-get install -y \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into the container
COPY . .

# Generate the opening book binary inside the container
RUN python generate_book.py

# Expose port and launch with Gunicorn
ENV PORT=10000
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app