# Setup Guide — ICC Trading Assistant

This guide walks you through setting up the project from scratch. You do not need prior coding experience.

## What You Need Installed First

1. **Python 3.11+** — https://www.python.org/downloads/
2. **Node.js 18+** — https://nodejs.org/
3. **PostgreSQL 15+** — https://www.postgresql.org/download/
   - OR sign up for a free Supabase project: https://supabase.com
4. **VS Code** — https://code.visualstudio.com/

## Step 1 — Clone or Download This Project

If you have git:
```bash
git clone <your-repo-url>
cd icc-trading
```

If not, download and unzip, then open the folder in VS Code.

## Step 2 — Set Up the Backend

Open a terminal in VS Code (Terminal → New Terminal).

```bash
# Go into the backend folder
cd backend

# Create a Python virtual environment (keeps packages isolated)
python -m venv venv

# Activate it (Mac/Linux)
source venv/bin/activate

# Activate it (Windows)
venv\Scripts\activate

# Install all required packages
pip install -r requirements.txt
```

### Create your .env file

In the `backend/` folder, create a file called `.env`:

```
# Database connection string
DATABASE_URL=postgresql://localhost:5432/icc_trading

# If using Supabase, replace with your Supabase connection string
# DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres

# Secret key for webhook security (make this long and random)
WEBHOOK_SECRET=your-secret-token-here

# JWT secret for user auth (make this long and random)
JWT_SECRET=your-jwt-secret-here

# Environment
ENVIRONMENT=development
```

### Create the database

```bash
# Create the database (run from backend/ folder)
python scripts/create_db.py
```

### Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

You should see: `Uvicorn running on http://127.0.0.1:8000`

Open http://localhost:8000/docs to see the API documentation.

## Step 3 — Set Up the Frontend

Open a NEW terminal in VS Code.

```bash
# Go into the frontend folder
cd frontend

# Install all packages
npm install

# Create your .env.local file
```

Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Start the frontend

```bash
npm run dev
```

You should see: `Ready on http://localhost:3000`

Open http://localhost:3000 in your browser.

## Step 4 — Connect TradingView

1. In TradingView, create an alert
2. Under "Notifications", enable "Webhook URL"
3. Set URL to: `http://YOUR_SERVER_URL/api/v1/alerts/webhook`
4. Add header: `X-Webhook-Token: your-secret-token-here`
5. Set the alert message JSON (see example in `/docs/TRADINGVIEW_ALERT_FORMAT.md`)

For local testing, use ngrok to expose your local server:
```bash
ngrok http 8000
```

## Step 5 — Configure ICC Rules

Visit http://localhost:3000/settings to configure:
- Which sessions are allowed
- Minimum impulse size for Indication
- Retracement range for Correction
- Minimum RR for trade qualification
- Daily max loss and other risk rules

## Project Structure Explained

```
backend/app/
  main.py              ← Starts the server
  api/v1/              ← All API endpoints (routes)
  core/                ← Config, security, database connection
  db/                  ← Database session management
  models/              ← Database table definitions
  schemas/             ← Data validation shapes
  services/
    icc_engine/        ← The ICC evaluation logic lives here
      environment.py   ← Session, liquidity, bias checks
      indication.py    ← Indication scoring
      correction.py    ← Correction zone scoring
      continuation.py  ← Continuation trigger scoring
      risk.py          ← Risk rule enforcement
      evaluator.py     ← Combines all four modules

frontend/app/
  page.tsx             ← Dashboard home
  alerts/              ← Incoming alerts feed
  setup/               ← Setup detail view
  journal/             ← Trade journal
  analytics/           ← Performance analytics
  paper-trading/       ← Paper trade console
  settings/            ← ICC rule configuration
```
