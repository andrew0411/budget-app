# ledger/rules.py
from __future__ import annotations
import re
from typing import Optional
import sqlite3

def apply_category_rules(conn: sqlite3.Connection, *, payee: Optional[str], institution: Optional[str]) -> Optional[str]:
    """
    활성 룰을 우선순위(priority ASC)로 평가.
    match_type='contains' → pattern(소문자)이 payee/institution 소문자에 포함되면 매치
    match_type='regex'     → re.search(pattern, payee) 매치
    institution 컬럼이 설정된 룰은 동일 institution일 때만 매치.
    매치되면 해당 rule.category 반환. 없으면 None.
    """
    rows = conn.execute("SELECT * FROM rules WHERE enabled=1 ORDER BY priority ASC, id ASC").fetchall()
    p = (payee or "").lower()
    inst = (institution or "").lower()
    for r in rows:
        pat = (r["pattern"] or "")
        mtype = (r["match_type"] or "contains")
        inst_only = (r["institution"] or None)
        if inst_only and inst_only.lower() not in inst:
            continue
        ok = False
        if mtype == "contains":
            s = pat.lower()
            ok = (s in p) or (s in inst)
        elif mtype == "regex":
            try:
                if p and re.search(pat, p, flags=re.IGNORECASE):
                    ok = True
                elif inst and re.search(pat, inst, flags=re.IGNORECASE):
                    ok = True
            except re.error:
                # 잘못된 정규식은 무시
                ok = False
        if ok:
            return r["category"]
    return None
