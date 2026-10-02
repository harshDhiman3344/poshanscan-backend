# PoshanScan — Deployment & Integration Guide

How to take all four finished repos and turn them into one working, connected app. I went through all four codebases to write this — the steps below match what's actually in your code, not a generic template.

**Deploy order matters: CV service → Backend → Worker app + Dashboard.** Each step needs the URL from the step before it.

---

## ⚠️ One fix needed before deploying the backend

Your backend uses a **synchronous** SQLAlchemy engine (`create_engine`, not `create_async_engine`) in `app/core/database.py`, but `requirements.txt` only lists `asyncpg` (an async-only Postgres driver) — it's missing a **sync** driver. If you deploy with a Postgres `DATABASE_URL` as-is, it will crash on startup with a "can't find driver" error.

**Fix — add one line to `poshanscan-backend/requirements.txt`:**
```
psycopg2-binary>=2.9.9
```
Commit and push this before deploying. This is the only code change required; everything else below is configuration.

---

## Step 1 — Deploy the CV/ML Service (Yash)

**Platform: Hugging Face Spaces (free CPU tier, Docker SDK)**

1. Go to huggingface.co → New Space → pick **Docker** as the Space SDK (not Gradio/Streamlit)
2. Connect/push your `poshanscan-ml-cv-service` repo to that Space (Spaces work like a git remote — you can push your existing repo straight to it)
3. Hugging Face will detect your `Dockerfile` automatically and build it — note it already `EXPOSE`s port 8001 and runs `uvicorn app.main:app --host 0.0.0.0 --port 8001`, which is exactly what Spaces expects
4. Once built, your service will be live at:
   ```
   https://<your-username>-<space-name>.hf.space
   ```
5. **Test it directly before moving on:**
   ```bash
   curl https://<your-username>-<space-name>.hf.space/health
   # should return {"status":"ok"}
   ```
   Also open `https://<your-username>-<space-name>.hf.space/docs` — your FastAPI Swagger UI — and try `POST /infer` with a test image to confirm the whole pipeline runs on the hosted environment, not just locally.

**Keep this URL — you need it for Step 2.**

---

## Step 2 — Deploy the Backend (Harsh)

**Platform: Render (free web service) + Supabase (free Postgres)**

### 2a. Set up the database
1. Create a free project at supabase.com
2. Go to Project Settings → Database → copy the **connection string** (URI format), it looks like:
   ```
   postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
   ```

### 2b. Deploy the backend on Render
1. Render → New → Web Service → connect your `poshanscan-backend` GitHub repo
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set these environment variables in Render's dashboard (matching your `.env.example`):

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your Supabase connection string from step 2a |
| `JWT_SECRET` | Generate a real random secret — **do not** use the placeholder value from `.env.example` in production |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` |
| `CV_SERVICE_URL` | Your Hugging Face Space URL from Step 1 (e.g. `https://yourname-poshanscan-cv.hf.space`) |
| `MOCK_CV` | `False` — **this is the switch that makes the backend call your real CV service instead of returning fake random results** |
| `UPLOAD_DIR` | `./uploads` |
| `DEBUG` | `False` |

5. Deploy. Render gives you a URL like:
   ```
   https://poshanscan-backend-xxxx.onrender.com
   ```

### 2c. Seed the database (so there's something to log in with)
Run this once, either locally with `DATABASE_URL` pointed at Supabase, or via Render's shell:
```bash
python seed.py
```
This creates demo accounts and sample locations/children/scans. Default seeded logins:

| Role | Phone | Password |
|---|---|---|
| Worker | `9876543210` | `worker123` |
| Supervisor | `9000000000` | `super123` |

**Test it:**
```bash
curl https://poshanscan-backend-xxxx.onrender.com/health
curl -X POST https://poshanscan-backend-xxxx.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"9876543210","password":"worker123"}'
```
You should get back a JWT access token. If this works, the backend-to-CV-service connection is also implicitly working the first time someone submits a real scan.

**Known limitation to know about (not a blocker):** `storage.py` saves uploaded images to local disk (`UPLOAD_DIR`). Render's free tier has an **ephemeral filesystem** — uploaded images will be lost on every redeploy or restart. This doesn't break the app (MUAC results are stored in Postgres either way), but raw images won't persist long-term on the free tier. Fine for your demo; worth knowing if you present this to your teacher.

---

## Step 3 — Deploy the Worker App (Navya)

**Platform: Vercel**

1. Vercel → New Project → import `poshanscan-worker-app`
2. Vercel auto-detects Vite — build command and output directory are already correct by default
3. Set environment variables (from your `.env.example`):

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | Your Render backend URL from Step 2 (e.g. `https://poshanscan-backend-xxxx.onrender.com`) |
| `VITE_REFERENCE_TYPE` | `aruco` |
| `VITE_REFERENCE_SIZE_MM` | `50` |
| `VITE_MIN_SHARPNESS` | `40` (tune later with real test photos) |

4. Deploy — the `vercel.json` already in your repo handles SPA routing correctly, no extra config needed
5. Open the deployed URL, log in with the worker credentials from Step 2c, and try a full scan

---

## Step 4 — Deploy the Dashboard (Dhruv)

**Platform: Vercel**

1. Vercel → New Project → import `PoshanScan-Dashboard`
2. Set environment variables:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | Same Render backend URL as Step 3 |
| `VITE_USE_MOCKS` | `false` — **important.** Your README shows this defaults to `true` (mock/demo mode with fake data via MSW). Leaving it `true` means the dashboard will show fake data forever and never actually call your backend. |

3. Deploy
4. Log in with the supervisor credentials from Step 2c (`9000000000` / `super123`) — not the worker account, since dashboard routes require the `supervisor` or `admin` role

---

## Step 5 — Full End-to-End Test

Once all four are deployed, do one real pass through the whole system:

1. Open the **worker app** URL → log in as worker → register a test child → capture a scan (real arm + printed ArUco marker, or a test image) → confirm you get back a real MUAC estimate (not obviously-random mock numbers)
2. Open the **dashboard** URL → log in as supervisor → confirm the scan you just submitted shows up in Overview stats and Trends
3. Turn on airplane mode on the phone you're testing the worker app with, do another scan, confirm it queues locally, then reconnect and confirm it syncs via `/sync`

If all three of those work, your four repos are now one connected, working app.

---

## Quick Reference — Final Architecture

```
┌─────────────────┐                    ┌──────────────────┐
│  WORKER APP       │ ──── HTTPS ────▶  │   BACKEND API      │
│  (Vercel)          │ ◀──────────────  │   (Render)          │
└─────────────────┘                    └─────────┬────────┘
                                                   │
                         ┌─────────────────────────┼─────────────────────┐
                         ▼                          ▼                      ▼
              ┌───────────────────┐    ┌──────────────────┐    ┌───────────────────┐
              │  CV/ML SERVICE      │    │  SUPABASE           │    │  DASHBOARD           │
              │  (Hugging Face)      │    │  (Postgres DB)       │    │  (Vercel)              │
              └───────────────────┘    └──────────────────┘    └───────────────────┘
```

| # | Repo | Owner | Platform | Needs URL from |
|---|---|---|---|---|
| 1 | `poshanscan-ml-cv-service` | Yash | Hugging Face Spaces | — (deploy first) |
| 2 | `poshanscan-backend` | Harsh | Render + Supabase | Step 1's CV URL |
| 3 | `poshanscan-worker-app` | Navya | Vercel | Step 2's backend URL |
| 4 | `PoshanScan-Dashboard` | Dhruv | Vercel | Step 2's backend URL |

---

## Troubleshooting Checklist

- **Worker app shows login error** → check `VITE_API_BASE_URL` has no trailing slash and points to the Render URL, not localhost
- **Scan always returns random-looking results** → `MOCK_CV` is still `True` on Render; flip it to `False` and redeploy
- **Dashboard shows fake demo data no matter what** → `VITE_USE_MOCKS` is still `true` on Vercel; flip it to `false` and redeploy
- **Backend crashes on startup after deploying** → almost certainly the missing `psycopg2-binary` fix from the top of this guide
- **First scan after inactivity takes ~30–60 seconds** → expected; both Render's free tier and Hugging Face Spaces cold-start after idling. Your worker app's `config.ts` already accounts for this with a 90-second `scanTimeoutMs` and an 8-second "server is waking up" hint — no fix needed, just open the backend/CV URLs a minute before any live demo to warm them up
- **CORS errors in browser console** → both your CV service and backend already have `allow_origins=["*"]` set, so this shouldn't happen; if it does, double check you're hitting the deployed URL and not an old cached one
