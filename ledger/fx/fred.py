# ledger/fx/fred.py
from __future__ import annotations
from typing import List, Dict
import os, json, requests
from datetime import date, timedelta
from pathlib import Path

FRED_SERIES = "DEXKOUS"
FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
SOURCE_LABEL = "FRED/DEXKOUS (H.10)"

def _load_api_key() -> str:
    key = os.getenv("FRED_API_KEY")
    if key:
        return key
    # fallback: secrets/.env에서 라인 파싱 (간단 로더)
    envp = Path(__file__).resolve().parents[2] / "secrets" / ".env"
    if envp.exists():
        for line in envp.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("FRED_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""

def fetch_dexkous(start: date, end: date) -> List[Dict]:
    """
    외부 API 호출 (FRED). inputs: start/end, api_key
    returns: [{"date":"YYYY-MM-DD","rate":float}]
    """
    key = _load_api_key()
    if not key:
        raise RuntimeError("FRED_API_KEY가 없어 요청을 보낼 수 없습니다. secrets/.env 또는 환경변수 설정필요.")

    params = {
        "series_id": FRED_SERIES,
        "api_key": key,
        "file_type": "json",
        "observation_start": start.strftime("%Y-%m-%d"),
        "observation_end": end.strftime("%Y-%m-%d"),
    }
    r = requests.get(FRED_OBS_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    return parse_observations(data)

def parse_observations(data: Dict) -> List[Dict]:
    """
    FRED series/observations JSON에서 유효값만 추출.
    value가 "."인 날짜는 제외.
    """
    out: List[Dict] = []
    for obs in data.get("observations", []):
        v = obs.get("value")
        if v is None or v == ".":
            continue
        try:
            out.append({"date": obs["date"], "rate": float(v)})
        except Exception:
            continue
    return out
