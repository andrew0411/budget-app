# tests/test_fx_fred.py
from ledger.fx.fred import parse_observations

def test_parse_observations_filters_dots():
    data = {"observations": [
        {"date": "2025-10-13", "value": "."},
        {"date": "2025-10-14", "value": "1429.91"},
    ]}
    out = parse_observations(data)
    assert len(out) == 1
    assert out[0]["date"] == "2025-10-14"
    assert out[0]["rate"] == 1429.91
