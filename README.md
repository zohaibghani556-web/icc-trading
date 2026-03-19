# ICC Futures Trading Assistant

> Decision-support, journaling, scoring, and research platform for futures day trading using the ICC (Indication, Correction, Continuation) framework.

## What This Does

This is **not** an auto-trading bot. It is a professional decision-support platform that:

1. Receives alerts from TradingView via webhook
2. Evaluates whether a valid ICC setup exists (and explains why)
3. Scores setup quality across four categories (Environment, Indication, Correction, Continuation)
4. Logs every setup and trade with full detail
5. Supports paper trading with realistic simulation
6. Enables post-trade review and failure labeling
7. Builds an analytics database so you can learn what works

## Quick Start

See `/docs/SETUP.md` for complete setup instructions.

```
backend/    → Python FastAPI (runs on localhost:8000)
frontend/   → Next.js dashboard (runs on localhost:3000)
docs/       → Setup guides and documentation
scripts/    → Database setup and utility scripts
```

## Supported Markets

ES, MES, NQ, MNQ, YM, MYM, CL, MCL, GC, MGC

## Architecture

- **Backend**: Python FastAPI + PostgreSQL
- **Frontend**: Next.js 14 (App Router)
- **Database**: PostgreSQL (local or Supabase)
- **Deployment**: Vercel (frontend) + Railway/Render (backend)

## Version

MVP v1.0 — Rule-based decision support only. No live auto-execution.
