# Multi-stage Dockerfile for InvoiceIQ on Render

# ------------------------------------------------------------------------------
# Stage 1: Build the React Frontend
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
# Build production bundle into /app/frontend/dist
ENV VITE_API_URL=""
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python Backend with Tesseract OCR & Production Server
# ------------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Tesseract OCR for scanned invoices
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend application source
COPY backend/ ./backend/

# Copy compiled frontend from Stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure SQLite data and upload directories exist
RUN mkdir -p /app/backend/data/uploads

ENV ENVIRONMENT=production \
    DEBUG=False \
    HOST=0.0.0.0 \
    PORT=10000 \
    DATABASE_URL=sqlite:///./data/invoiceiq.db \
    ALLOWED_ORIGINS=*

EXPOSE 10000

WORKDIR /app/backend

# Render sets PORT dynamically, so we bind to $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
