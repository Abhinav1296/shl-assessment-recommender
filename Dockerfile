FROM python:3.11-slim

# System deps for sentence-transformers / torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model into the image (avoids cold-start delay on HF)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy app code
COPY . .

# HF Spaces uses port 7860
ENV PORT=7860
EXPOSE 7860

# Cache dir for HF models (HF Spaces writable path)
ENV HF_HOME=/app/.cache/huggingface

CMD ["python", "main.py"]