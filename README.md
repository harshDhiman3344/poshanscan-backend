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

## 🚀 Features & API Specification

### 1. Authentication & RBAC
- **Frontline Worker & Shared Auth:** `POST /auth/login` (Accepts `{phone, password}`, returns `{access_token, token, role, name, user_id}`).
- **Dedicated Supervisor Portal Auth:** `POST /supervisor/login` (Dedicated for supervisors & admins; rejects frontline workers with `403 Forbidden`).
- **Profile:** `GET /auth/me` (Returns current authenticated user details).

### 2. Frontline Worker Endpoints (Navya - Worker PWA)
- **`GET /children/search?q={query}`**: Search children by name, guardian, village, or ID.
- **`POST /children`**: Register new child profile.
- **`POST /scans`**: Online single scan.
  - Form fields: `image` (file), `child_id`, `worker_id`, `reference_type`, `reference_size_mm`, `age_category` (`child_6_59m` or `adult`, default: `child_6_59m`).
  - Forwards to CV service and returns `ScanResultResponse`.
- **`POST /sync`**: Offline batch sync.
  - Multipart: `metadata` (JSON array of scan items including `age_category`), `images` (matching photos).
  - Handles idempotency via `client_scan_id`.

### 3. Supervisor Dashboard Endpoints (Dhruv - Supervisor Portal)
Primary endpoints are prefixed with `/supervisor/dashboard/...` (legacy `/dashboard/...` remains active as an alias):

| Method | Endpoint | Description | Query Parameters |
|---|---|---|---|
| `POST` | `/supervisor/login` | Supervisor/Admin authentication | — |
| `GET` | `/supervisor/dashboard/overview` | Screenings total, Normal/MAM/SAM breakdown, confidence | `age_category` (`child_6_59m`, `adult`, `all`) |
| `GET` | `/supervisor/dashboard/trends` | Time-series screening numbers for Recharts | `days`, `from`, `to`, `group_by`, `interval`, `age_category` |
| `GET` | `/supervisor/dashboard/locations` | Village-level malnutrition rates & coordinates for Leaflet | `age_category` |
| `GET` | `/supervisor/dashboard/workers` | Worker activity, screening counts, and assigned villages | `age_category` |
| `GET` | `/supervisor/dashboard/flagged` | Scans requiring review (SAM or confidence < 0.60) | `status` (`pending`, `reviewed`), `age_category` |
| `POST` | `/supervisor/dashboard/flagged/{id}/review` | Mark a flagged scan as reviewed | — |
| `GET` | `/supervisor/dashboard/export` | District health report CSV download | — |

*Note on Age Category Filtering:* Adult demo scans are automatically excluded from the overview stats, trends charts, and village maps by default (`age_category=child_6_59m`) so demoing on adults never skews child malnutrition data.

### 4. Computer Vision Microservice Integration (Yash)
- Central backend forwards multipart requests to Yash's `POST /infer` endpoint with `reference_type`, `reference_size_mm`, and `age_category`.
- Built-in dual-scale simulation engine (`MOCK_CV=True`) supporting:
  - **Child (`child_6_59m`):** `<115mm` SAM, `115–124.9mm` MAM, `≥125mm` Normal.
  - **Adult (`adult`):** `<210mm` SAM, `210–229mm` MAM, `≥230mm` Normal.

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

### 4. Database Migration & Seed
Initializes tables, runs automated migrations (e.g. `age_category` column), and seeds 150+ realistic multi-worker records:
```bash
python seed.py
```

### 5. Run the Server
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger API docs: **http://localhost:8000/docs**

---

## 🔑 Seeded Default Credentials

| Role | Username / Phone | Password | Allowed Logins |
|---|---|---|---|
| **Frontline Worker** | `9876543210` | `worker123` | `POST /auth/login` |
| **Field Workers (2-4)** | `9876543211` - `9876543213` | `worker123` | `POST /auth/login` |
| **Supervisor** | `9000000000` | `super123` | `POST /supervisor/login`, `POST /auth/login` |
| **Admin** | `admin` | `admin` | `POST /supervisor/login`, `POST /auth/login` |

---

## 🧪 Running Tests
```bash
pytest tests/ -v
```
