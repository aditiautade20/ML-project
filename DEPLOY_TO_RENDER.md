# InvoiceIQ — Deployment Guide for Render (render.com)

This guide walks you through deploying **InvoiceIQ** (FastAPI backend + React Vite frontend) to **Render** step-by-step.

---

## Table of Contents
1. [Deployment Methods Summary](#1-deployment-methods-summary)
2. [Prerequisites: Push Project to GitHub](#2-prerequisites-push-project-to-github)
3. [Method 1: Automatic 1-Click Blueprint Deployment (Recommended)](#3-method-1-automatic-1-click-blueprint-deployment-recommended)
4. [Method 2: Single Full-Stack Web Service (Monolith)](#4-method-2-single-full-stack-web-service-monolith)
5. [Method 3: Manual Step-by-Step Dashboard Setup](#5-method-3-manual-step-by-step-dashboard-setup)
6. [Method 4: Containerized Deployment (Docker with Tesseract OCR)](#6-method-4-containerized-deployment-docker-with-tesseract-ocr)
7. [Environment Variables Reference](#7-environment-variables-reference)
8. [Seeding the Demo Account on Render](#8-seeding-the-demo-account-on-render)
9. [Important Render Free Tier Notes & Tips](#9-important-render-free-tier-notes--tips)

---

## 1. Deployment Methods Summary

| Method | Services on Render | Best For | OCR Scans | Setup Effort |
|---|---|---|---|---|
| **Method 1: Blueprint (`render.yaml`)** | 1 Web Service (Backend) + 1 Static Site (Frontend) | Standard production architecture, fast global CDN for frontend | Digital PDFs + Images | **1-Click** (Fastest) |
| **Method 2: Single Service (`render-build.sh`)** | 1 Web Service (Backend serving compiled React build) | Simplest setup, zero CORS configuration, uses only 1 free service | Digital PDFs + Images | Low |
| **Method 3: Manual Setup** | Web Service + Static Site created manually in UI | Complete custom control via Render Dashboard | Digital PDFs + Images | Medium |
| **Method 4: Dockerfile** | 1 Docker Web Service | Complete Linux packages including system Tesseract OCR | Full OCR + Digital PDFs | Low |

---

## 2. Prerequisites: Push Project to GitHub

Render deploys directly from your GitHub or GitLab repository. If you haven't initialized Git yet, run these commands in your project root:

```bash
# 1. Initialize git repository
git init

# 2. Add all files
git add .

# 3. Create initial commit
git commit -m "Initial commit for InvoiceIQ with Render deployment config"

# 4. Create a new repository on GitHub (https://github.com/new) named "InvoiceIQ"
# Then link and push:
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/InvoiceIQ.git
git push -u origin main
```

---

## 3. Method 1: Automatic 1-Click Blueprint Deployment (Recommended)

InvoiceIQ includes a pre-configured `render.yaml` file in the root directory.

1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click the **New +** button at the top right and select **Blueprint**.
3. Connect your GitHub account and select your **InvoiceIQ** repository.
4. Render automatically parses `render.yaml` and detects two services:
   - `invoiceiq-backend` (Python Web Service)
   - `invoiceiq-frontend` (Static Site)
5. Review the plan (both set to **Free**).
6. Click **Apply**.
7. Render will automatically:
   - Build and deploy the FastAPI backend.
   - Inject the backend's live URL into the frontend build (`VITE_API_URL`).
   - Configure the client-side SPA routing rewrite (`/*` -> `/index.html`).
   - Launch both services with free SSL certificates (`https://...`).

---

## 4. Method 2: Single Full-Stack Web Service (Monolith)

If you want to use only **one free Web Service** on Render, InvoiceIQ's backend is configured to automatically serve the built React frontend when compiled into `frontend/dist`.

1. Go to [Render Dashboard](https://dashboard.render.com) -> Click **New +** -> **Web Service**.
2. Select your repository.
3. Configure the following:
   - **Name:** `invoiceiq-app`
   - **Region:** Any (e.g., Oregon or Frankfurt)
   - **Branch:** `main`
   - **Root Directory:** *(leave blank / root)*
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     bash render-build.sh
     ```
   - **Start Command:**
     ```bash
     cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** `Free`
4. Add the following **Environment Variables** in the Environment tab:
   - `PYTHON_VERSION` = `3.11.9`
   - `ENVIRONMENT` = `production`
   - `DEBUG` = `False`
   - `SECRET_KEY` = *(click "Generate" or type a random 32+ character string)*
   - `DATABASE_URL` = `sqlite:///./data/invoiceiq.db`
   - `ALLOWED_ORIGINS` = `*`
5. Click **Create Web Service**.
6. When the build finishes, open the live URL. Both the React UI and FastAPI API will be running seamlessly on the exact same domain with **zero CORS issues**.

---

## 5. Method 3: Manual Step-by-Step Dashboard Setup

If you prefer to configure the backend and frontend separately via the Render UI:

### Step 5.1: Create the Backend Web Service
1. In Render, click **New +** -> **Web Service**.
2. Select your repository.
3. Fill in the fields:
   - **Name:** `invoiceiq-backend`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`
4. Under **Advanced** -> **Health Check Path**, enter: `/api/health`.
5. Under **Environment Variables**, add:
   - `PYTHON_VERSION` = `3.11.9`
   - `ENVIRONMENT` = `production`
   - `DEBUG` = `False`
   - `SECRET_KEY` = *(generate random string)*
   - `DATABASE_URL` = `sqlite:///./data/invoiceiq.db`
   - `ALLOWED_ORIGINS` = `*`
6. Click **Create Web Service** and wait for deployment.
7. Note down your backend URL (e.g., `https://invoiceiq-backend.onrender.com`).

---

### Step 5.2: Create the Frontend Static Site
1. In Render, click **New +** -> **Static Site**.
2. Select your repository.
3. Fill in the fields:
   - **Name:** `invoiceiq-frontend`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm install && npm run build`
   - **Publish Directory:** `dist`
4. Under **Redirects/Rewrites**:
   - Click **Add Rule**
   - **Type:** `Rewrite`
   - **Source:** `/*`
   - **Destination:** `/index.html`
   *(This ensures React Router routes like `/dashboard`, `/invoices`, `/reconciliation` load properly on page refresh).*
5. Under **Environment Variables**, add:
   - `VITE_API_URL` = `https://invoiceiq-backend.onrender.com` *(use your backend URL from Step 5.1)*
6. Click **Create Static Site**.

---

## 6. Method 4: Containerized Deployment (Docker with Tesseract OCR)

InvoiceIQ also includes a multi-stage `Dockerfile` that packages:
- The compiled React 18 frontend
- The Python 3.11 FastAPI backend
- The Linux `tesseract-ocr` system package for scanned/image OCR processing

1. In Render, click **New +** -> **Web Service**.
2. Select your repository.
3. Set **Runtime** to `Docker`.
4. Render will automatically detect the root `Dockerfile`.
5. Set **Environment Variables**:
   - `SECRET_KEY` = *(random string)*
   - `DATABASE_URL` = `sqlite:///./data/invoiceiq.db`
6. Click **Create Web Service**.

---

## 7. Environment Variables Reference

| Variable | Recommended Production Value | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Disables debug logs and development banners |
| `DEBUG` | `False` | Hides internal tracebacks and secures API docs |
| `HOST` | `0.0.0.0` | Binds to all network interfaces on Render |
| `PORT` | *(Render provides this dynamically)* | Application port (usually 10000) |
| `SECRET_KEY` | *(32+ character random string)* | Used for cryptographic JWT token signing |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token validity duration |
| `DATABASE_URL` | `sqlite:///./data/invoiceiq.db` | Path to SQLite database (or Render PostgreSQL URL) |
| `ALLOWED_ORIGINS` | `*` or `https://your-frontend.onrender.com` | Allowed CORS origins for browser security |
| `VITE_API_URL` | `https://your-backend.onrender.com` | Backend API base URL used by React frontend |

---

## 8. Seeding the Demo Account on Render

Once your backend is live, you can populate the dedicated showcase account (`demo@invoiceiq.local` / `DemoUser123!`) with 10 realistic invoices and reconciliation records:

1. Open your backend service in the Render Dashboard.
2. Click the **Shell** tab in the left sidebar to open a web terminal in your running container.
3. Run:
   ```bash
   python -m app.demo_seed --seed
   ```
4. Output will confirm:
   ```
   Created demo user: demo@invoiceiq.local
   Successfully seeded 10 demo invoices and associated payments.
   Isolation Forest anomaly assessment executed.
   ```
5. You can now log into your live web app using:
   - **Email:** `demo@invoiceiq.local`
   - **Password:** `DemoUser123!`

---

## 9. Important Render Free Tier Notes & Tips

1. **Free Tier Cold Starts (Sleep Mode):**
   - On the Render Free plan, Web Services spin down after 15 minutes of inactivity.
   - When you visit your site after inactivity, the first request may take ~30–50 seconds while the container boots up. Subsequent requests are instant.
   - *Tip:* You can use a free ping monitor service like [UptimeRobot](https://uptimerobot.com) to ping `https://your-backend.onrender.com/api/health` every 10 minutes to keep it awake during demo presentations!

2. **Database Persistence:**
   - On the Render Free plan, the local filesystem is ephemeral (it resets whenever the service redeploys or restarts).
   - If you want permanent database persistence that survives redeployments:
     - In Render, click **New +** -> **PostgreSQL** (Free 1GB database).
     - Copy the **Internal Database URL** (e.g., `postgresql://user:pass@dpg-xxx/invoiceiq_db`).
     - Paste it as the `DATABASE_URL` environment variable in your Backend Web Service.
     - InvoiceIQ uses standard SQLAlchemy models and will automatically initialize tables on PostgreSQL!

3. **HTTPS / SSL:**
   - Render automatically provisions free, auto-renewing Let's Encrypt SSL certificates for all `.onrender.com` domains and custom domains.
