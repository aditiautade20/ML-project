#!/usr/bin/env bash
# Exit on any error
set -o errexit

echo "=========================================="
echo " Starting InvoiceIQ Render Full-Stack Build"
echo "=========================================="

# 1. Install & build frontend static assets
echo "--> Building React frontend..."
cd frontend
npm install
npm run build
cd ..

# 2. Install backend Python dependencies
echo "--> Installing backend Python dependencies..."
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo "=========================================="
echo " InvoiceIQ Build Succeeded!"
echo "=========================================="
