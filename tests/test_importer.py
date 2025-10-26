import pandas as pd

from ledger.importer import Mapping, Defaults, map_df_to_txns


def test_mapping_and_direction():
    df = pd.DataFrame(
        {
            "d": ["2025-10-01 12:00", "2025-10-02 08:00"],
            "amt": [-1000, 2000],
            "c": ["KRW", "KRW"],
            "p": ["Shop", "Company"],
            "cat": ["Food", "Income"],
        }
    )
    m = Mapping(date="d", amount="amt", currency="c", payee="p", category="cat")
    txns = map_df_to_txns(df, m, Defaults(currency="KRW"))
    assert len(txns) == 2
    assert txns[0]["direction"] == "debit"
    assert txns[1]["direction"] == "credit"
    assert txns[0]["amount"] == 1000.0
    assert txns[0]["currency"] == "KRW"
