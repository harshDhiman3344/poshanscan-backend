# PoshanScan Backend API (`poshanscan-backend`)

The central coordination, API gateway, and relational storage microservice for **PoshanScan: AI-Assisted Smartphone-Based MUAC Screening and Digital Monitoring System**.

Designed and built by **Harsh Dhiman (Backend & System Integration Engineer)**.

---

## 🏗️ Architecture

```
[Navya: Worker PWA] ─────────┐
                             │ HTTP (JWT Auth)
                             ▼
               ┌───────────────────────────┐
               │    PoshanScan Backend     │
               │         (FastAPI)         │
               └─────────────┬─────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │ (HTTP Multipart)    │ (SQLAlchemy)        │ (Aggregate APIs)
       ▼                     ▼                     ▼
[Yash: AI/CV Service]  [PostgreSQL / Supabase]  [Dhruv: Dashboard]
 (OpenCV + YOLO +       (Relational Database)    (React + Recharts)
  MediaPipe on HF)
```

---

## 🚀 Features

1. **Authentication & RBAC:**
   - JWT tokens with role-based access (`worker`, `supervisor`, `admin`).
   - Secure bcrypt password hashing.
2. **Worker PWA Endpoints (Navya):**
   - `POST /auth/login`
   - `GET /children/search?q={query}`
   - `POST /children`
   - `POST /scans` (Online single scan forwarded to CV service)
   - `POST /sync` (Offline queue batch upload with idempotency keys)
3. **AI/CV Integration (Yash):**
   - Async forwarding to Yash's `POST /infer` endpoint.
   - Error mapping for unprocessable frames (`reference_object_not_detected`, `arm_not_detected`).
   - Built-in `MOCK_CV=True` mode for offline/isolated backend development.
4. **Supervisor Analytics Endpoints (Dhruv):**
   - `GET /dashboard/overview` (Total screenings, Normal/MAM/SAM counts, avg confidence).
   - `GET /dashboard/trends` (Time-series data for charts).
   - `GET /dashboard/locations` (Village-level malnutrition prevalence for maps).
   - `GET /dashboard/workers` (Worker screening counts & activity).
   - `GET /dashboard/flagged` (Low-confidence or SAM records for review).
   - `GET /dashboard/export` (CSV export).

---

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+ (Python 3.11 recommended)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Seed Test Data
Populates default accounts and sample children matching the worker app:
```bash
python seed.py
```
Default accounts created:
* **Worker:** `9876543210` / `worker123`
* **Supervisor:** `9000000000` / `super123`

### 5. Run the Server
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger API docs available at: **http://localhost:8000/docs**

---

## 🧪 Running Tests
```bash
pytest tests/ -v
```
