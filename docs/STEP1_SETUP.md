# Step 1 — Get the Backend Running

**Goal:** Server starts, database tables are created, you can open `http://localhost:8000/docs`
and see the API explorer. Nothing else yet.

---

## What you need installed first

Before starting, make sure these are installed on your computer.
Each one has a download link — just install with defaults.

| Tool | Why | Download |
|------|-----|----------|
| Python 3.11 or newer | Runs the backend | https://www.python.org/downloads/ |
| VS Code | Code editor | https://code.visualstudio.com/ |
| PostgreSQL 16 | Database | https://www.postgresql.org/download/ |

> **No PostgreSQL?** You can use Supabase instead (free cloud database).
> Sign up at https://supabase.com, create a project, and skip the PostgreSQL install steps below.

---

## Part A — Create the database

### If using local PostgreSQL:

After installing PostgreSQL, open a terminal and type:

```
psql -U postgres
```

It will ask for a password (whatever you set during install). Then type:

```sql
CREATE DATABASE icc_trading;
\q
```

That creates the empty database. The app will create all the tables inside it automatically.

### If using Supabase:

1. Go to https://supabase.com and sign up
2. Click "New Project"
3. Give it a name like `icc-trading`, set a password, pick a region
4. Wait for it to finish (about 60 seconds)
5. Go to **Settings → Database → Connection string → URI**
6. Copy the connection string — you'll need it in Part B

---

## Part B — Set up your .env file

The `.env` file contains your database password and secret keys.
It lives inside the `backend/` folder and is never shared or committed.

1. Open VS Code
2. Open the `icc-trading` folder (File → Open Folder)
3. In the left panel, find `backend/.env.example`
4. Right-click it → **Copy**
5. Right-click the `backend` folder → **Paste**
6. Rename the copy to `.env` (remove the `.example` part)
7. Open `.env` and edit the `DATABASE_URL` line:

**If local PostgreSQL:**
```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/icc_trading
```
Replace `YOUR_PASSWORD` with your PostgreSQL password.

**If Supabase:**
```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_ID.supabase.co:5432/postgres
```
Paste the connection string you copied, but change `postgresql://` to `postgresql+asyncpg://`.

Save the file.

---

## Part C — Install Python packages

Open a terminal in VS Code (menu: **Terminal → New Terminal**).

Make sure you're in the `backend` folder:
```
cd backend
```

Create a virtual environment (an isolated box for Python packages):

**Mac / Linux:**
```
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```
python -m venv venv
venv\Scripts\activate
```

You should now see `(venv)` at the start of your terminal line.

Install all packages:
```
pip install -r requirements.txt
```

This takes about a minute. Wait for it to finish.

---

## Part D — Verify everything is wired up

Still in the `backend` folder with `(venv)` active, run:

```
python scripts/verify_setup.py
```

You should see a list of green checkmarks. If anything shows a red ❌, the message will tell you exactly what to fix.

**Common issues:**
- `Missing package` → re-run `pip install -r requirements.txt`
- `.env file missing` → make sure you renamed `.env.example` to `.env`
- `Config error: DATABASE_URL` → double-check your DATABASE_URL in `.env`

---

## Part E — Start the server

```
uvicorn app.main:app --reload --port 8000
```

You should see output like:
```
✅ Database tables ready
✅ ICC Trading Assistant running in development mode
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## Part F — Seed the database with default data

Open a **second terminal** (keep the server running in the first one).

In the new terminal, go back to the `backend` folder and activate the venv:

**Mac / Linux:**
```
cd backend
source venv/bin/activate
python scripts/seed_db.py
```

**Windows:**
```
cd backend
venv\Scripts\activate
python scripts/seed_db.py
```

You should see:
```
✅ Seed complete
   Created: ES1!, MES1!, NQ1!, MNQ1!, YM1!, MYM1!, CL1!, MCL1!, GC1!, MGC1!, Default ICC config
```

---

## ✅ Step 1 Complete — Test it

Open your browser and go to:

```
http://localhost:8000/docs
```

You should see a page titled **ICC Trading Assistant** with a list of all API endpoints.

Click on **GET /** (the first one), then click **"Try it out"** → **"Execute"**.
You should get back:
```json
{
  "status": "online",
  "service": "ICC Trading Assistant",
  "version": "1.0.0",
  "environment": "development"
}
```

**That's Step 1 done.** The backend is running, the database tables exist, and the API is live.

---

## Troubleshooting

**"connection refused" when starting the server**
→ Your PostgreSQL isn't running. On Mac: open the PostgreSQL app in your Applications folder. On Windows: search for "Services", find PostgreSQL, right-click → Start.

**"password authentication failed"**
→ The password in your `.env` DATABASE_URL doesn't match your PostgreSQL password. Try connecting with `psql -U postgres` to confirm what password works.

**"module not found" errors**
→ Your virtual environment isn't active. Run `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows) first.

**Port 8000 already in use**
→ Something else is using that port. Use port 8001 instead: `uvicorn app.main:app --reload --port 8001`

---

## What was just created in the database?

When the server started, it automatically created these tables:
- `raw_alerts` — stores every webhook payload from TradingView
- `signals` — normalized alert data
- `setup_evaluations` — ICC scoring results
- `trades` — paper trade records
- `trade_reviews` — post-trade review labels
- `users` — user accounts (for later)
- `instruments` — the 10 supported futures contracts
- `icc_configurations` — your ICC rule settings

When you ran `seed_db.py`, it filled in the 10 instruments and created a default ICC configuration with sensible starting thresholds.

---

**Next:** Say "Step 2" to build and test the ICC engine with a real evaluation.
