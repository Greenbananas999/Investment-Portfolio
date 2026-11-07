"""Merge the fixed universe rows and the per-type long lists into universe.csv.

    python research/plan/merge_universe.py

Reads research/plan/universe_fixed.csv and research/plan/longlists/{us_growth,
intl_growth,em_bonds,other}.csv (same 17 columns), drops exact duplicate
tickers (first occurrence wins, fixed rows first), checks that every currency
in the long lists has an FX row, and writes research/plan/universe.csv.
Overlays are an inventory (overlays.csv), not tickers, so they are not merged.
"""

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
COLS = ("ticker,name,type,role,country,currency,listing,usd_ticker,local_index,"
        "edgar_cik,since,market_cap_usd_bn,aum_usd_bn,expense_ratio,category,notes,source_url").split(",")
LISTS = ["us_growth", "intl_growth", "em_bonds", "other"]


def main():
    frames = [pd.read_csv(HERE / "universe_fixed.csv", dtype=str)]
    for name in LISTS:
        df = pd.read_csv(HERE / "longlists" / f"{name}.csv", dtype=str)
        assert list(df.columns) == COLS, f"{name}.csv columns differ from the schema"
        df["source_list"] = name
        frames.append(df)
    u = pd.concat(frames, ignore_index=True).fillna("")
    u["source_list"] = u["source_list"].replace("", "fixed")
    u["ticker"] = u["ticker"].str.strip()
    # A ticker that is both a benchmark (fixed row) and a candidate (long list)
    # keeps the candidate row, so the screens see it, and records the benchmark
    # role in notes. Otherwise the first occurrence wins.
    is_fixed = u["source_list"] == "fixed"
    u["_order"] = is_fixed.astype(int)  # long-list rows first
    u = u.sort_values("_order", kind="stable")
    for t, grp in u[u.duplicated("ticker", keep=False)].groupby("ticker"):
        kept = grp.index[0]
        for i in grp.index[1:]:
            tag = f"also {u.at[i, 'type']}:{u.at[i, 'category']}" if u.at[i, "category"] else f"also {u.at[i, 'type']}"
            u.at[kept, "notes"] = (u.at[kept, "notes"] + "; " + tag).strip("; ")
            print(f"duplicate {t}: kept {u.at[kept, 'source_list']} row, merged note '{tag}'")
    u = u.drop_duplicates("ticker", keep="first").sort_values("_order", kind="stable").drop(columns="_order")
    u["edgar_cik"] = u["edgar_cik"].str.replace(r"\.0$", "", regex=True).str.zfill(10).where(u["edgar_cik"] != "", "")
    fx_ccys = set(u.loc[u.type == "fx", "currency"]) | {"USD"}
    need = set(u.loc[u.type.isin(["us_growth_stock", "intl_growth_stock", "em_bond", "other"]), "currency"]) - {"LOCAL", "MIXED", ""}
    missing = sorted(need - fx_ccys)
    if missing:
        print("WARNING: no FX row for currencies:", missing)
    u.to_csv(HERE / "universe.csv", index=False)
    print(f"universe.csv: {len(u)} rows")
    print(u.groupby(["type", "role"]).size().to_string())


if __name__ == "__main__":
    main()
