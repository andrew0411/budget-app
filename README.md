# Local Budget App 💸

A friendly, local-first personal finance tracker built with **Streamlit** and **SQLite**.  
**Language:** English UI with **Korean labels supported** (pages and fields include simple EN/KR wording).

---

## ✨ Features

- **Dashboard:** total assets, month-to-date (MTD) spend, per-account balances (table + chart)
- **Transactions:** view, inline edit, soft-delete/restore; re-apply category rules on demand
- **CSV Import:** flexible column mapping, duplicate detection, **auto-create missing accounts** (optional), **category rules** (optional)
- **Accounts:** manage bank/card/cash/brokerage/other accounts
- **Bank/Card Breakdown:** spending grouped by institution (bank/card)
- **Budget:** enter monthly budgets and compare **budget vs. actual** with progress badges
- **Rules:** category auto-classification (contains/regex, optional institution filter, priority)
- **Backups:** daily automatic backup + manual backup from the sidebar
- **FX (optional):** FRED DEXKOUS (USD→KRW) fetch with local cache

---

## Prerequisites

- **Python** 3.11, Streamlit
- **Conda** (Anaconda/Miniconda)
- OS: Windows/macOS/Linux

---

## 🚀 Quick Start (Conda)

```bash
# 1) Clone
git clone <your-repo-url> budget-app
cd budget-app

# 2) Create env (first time)
conda create -n streamlit-app python=3.11 -y

# 3) Install deps (prefer conda-forge)
conda install -n streamlit-app -c conda-forge streamlit pandas numpy altair scipy python-dotenv pytest -y

# 4) (Optional) set up FRED API (see "Secrets" below)

# 5) Run the app
conda run -n streamlit-app python -m streamlit run app/main.py
```

## 🔐 Secrets (FRED FX, optional)
If you want USD→KRW FX via FRED (series DEXKOUS):
1. Get a free API key from FRED: https://fred.stlouisfed.org/
2. Create a local file at `secrets/.env`:

```
# secrets/.env
FRED_API_KEY=YOUR_FRED_API_KEY
```

## Tests
```bash
conda run -n streamlit-app python -m pytest -q
```

## 🪟 Using on Windows: double-click to launch
Create `run_budget_app.bat` at the repo root:
```bat
@echo off
cd /d "%~dp0"
conda run -n streamlit-app --no-capture-output python -m streamlit run app\main.py --server.headless=false
```
- Make a **Desktop shortcut** to this `.bat` and double-click to open the app in your default browser.
