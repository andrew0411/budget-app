# Budget App — Beginner-Friendly, Local-First

- UI: Streamlit (pastel, emoji categories, EN/KR labels)
- Analytics: MoM %, Theil–Sen slope, Mann–Kendall trend badge (later)
- FX: FRED DEXKOUS (KRW per USD) with daily cache (later)
- Storage: SQLite + CSV export + daily backups (later)

## Run (conda)
```powershell
conda activate budget-app
python -m streamlit run app/Main.py
pytest -q
