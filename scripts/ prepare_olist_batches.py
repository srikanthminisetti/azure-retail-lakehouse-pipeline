#!/usr/bin/env python3
"""
Turn the raw Olist Kaggle CSVs into a simulated *source system* that delivers
data in monthly batches, so the pipeline has a real incremental-load problem.

Layout produced:
  <output-dir>/<table>/batch_date=YYYY-MM-DD/<table>.csv
  <output-dir>/manifest.json   <- expected counts (your test oracle)

What is simulated (and documented as simulated in the README):
  * Transactional tables (orders, order_items, order_payments, order_reviews)
    are split into month-end batches.
  * Orders that change state across months arrive twice: an early 'processing'
    snapshot, then the final record in a later batch  -> needs MERGE (upsert).
  * ~0.5-1% duplicate rows are re-delivered (same batch and next batch).
  * A small number of clearly-marked BAD rows (order_id starts with BAD...) are
    injected so the data-quality gates have something to catch.
Reference tables (customers, products, sellers, geolocation, category translation)
are delivered once as a full load.

Usage:
  python scripts/prepare_olist_batches.py --input-dir data/raw --output-dir data/source
"""
import argparse, json, shutil
from pathlib import Path
import numpy as np
import pandas as pd

INITIAL_BATCH = "2016-01-01"
ORDER_TS = ["order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date"]
FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}
KEYS = {
    "orders": ["order_id"], "order_items": ["order_id", "order_item_id"],
    "order_payments": ["order_id", "payment_sequential"],
    "order_reviews": ["review_id", "order_id"], "customers": ["customer_id"],
    "products": ["product_id"], "sellers": ["seller_id"], "geolocation": None,
    "category_translation": ["product_category_name"],
}


def read(inp: Path, table: str) -> pd.DataFrame:
    # dtype=str + no NA parsing => bronze stays byte-for-byte "raw"
    return pd.read_csv(inp / FILES[table], dtype=str, keep_default_na=False)


def month_end(s: pd.Series) -> pd.Series:
    return (s + pd.offsets.MonthEnd(0)).dt.strftime("%Y-%m-%d")


def write_batches(out: Path, table: str, df: pd.DataFrame, cols, batch_col="_batch"):
    n = 0
    for batch, part in df.groupby(batch_col):
        d = out / table / f"batch_date={batch}"
        d.mkdir(parents=True, exist_ok=True)
        part[cols].to_csv(d / f"{table}.csv", index=False)
        n += len(part)
    return n, df[batch_col].nunique()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output-dir", default="data/source")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bad-rows", type=int, default=20, help="bad rows injected per transactional table")
    ap.add_argument("--no-inject", action="store_true", help="do not inject duplicates/bad rows")
    a = ap.parse_args()

    inp, out = Path(a.input_dir), Path(a.output_dir)
    if out.exists():
        shutil.rmtree(out)
    inject = not a.no_inject
    nbad = a.bad_rows if inject else 0
    man = {"seed": a.seed, "inject_issues": inject, "tables": {}}

    def record(table, orig, bronze_rows, batches, **extra):
        keys = KEYS[table]
        distinct = len(orig.drop_duplicates(subset=keys)) if keys else len(orig.drop_duplicates())
        man["tables"][table] = {"rows_original": len(orig), "distinct_key_rows": distinct,
                                "expected_silver_rows": distinct, "bronze_rows_written": bronze_rows,
                                "batches": batches, **extra}

    # ---------------- orders ----------------
    orders = read(inp, "orders")
    cols = list(orders.columns)
    ts = {c: pd.to_datetime(orders[c].replace("", np.nan), errors="coerce") for c in ORDER_TS}
    purchase = ts["order_purchase_timestamp"]
    assert purchase.notna().all(), "orders with no purchase timestamp"
    last_event = pd.concat([ts[c] for c in ORDER_TS[:4]], axis=1).max(axis=1).fillna(purchase)
    orders["_batch"], orders["_pbatch"] = month_end(last_event), month_end(purchase)

    snap = orders[orders["_batch"] != orders["_pbatch"]].copy()      # in-flight snapshot
    snap["order_status"] = "processing"
    for c in ORDER_TS[1:4]:
        snap[c] = ""
    snap["_batch"] = snap["_pbatch"]

    redeliver = orders.sample(frac=0.005 if inject else 0, random_state=a.seed).copy()
    if len(redeliver):
        redeliver["_batch"] = month_end(pd.to_datetime(redeliver["_batch"]) + pd.offsets.MonthEnd(1))

    bad = orders.sample(n=nbad, random_state=a.seed).reset_index(drop=True) if nbad else orders.iloc[0:0].copy()
    for i in range(len(bad)):
        bad.loc[i, "order_id"] = f"BADORD{i:05d}"
        k = i % 3
        if k == 0: bad.loc[i, "customer_id"] = ""
        elif k == 1: bad.loc[i, "order_status"] = "teleported"
        else: bad.loc[i, "order_delivered_customer_date"] = "2000-01-01 00:00:00"

    allo = pd.concat([orders, snap, redeliver, bad], ignore_index=True)
    n, nb = write_batches(out, "orders", allo, cols)
    record("orders", orders[cols], n, nb, status_snapshots_added=len(snap),
           redelivered_duplicates=len(redeliver), injected_bad_rows=len(bad))
    pbatch = orders.drop_duplicates("order_id").set_index("order_id")["_pbatch"]

    # ---------------- order_items ----------------
    items = read(inp, "order_items"); cols = list(items.columns)
    items["_batch"] = items["order_id"].map(pbatch)
    assert items["_batch"].notna().all(), "order_items referencing unknown orders"
    dup = items.sample(frac=0.01 if inject else 0, random_state=a.seed)
    bad = items.sample(n=nbad, random_state=a.seed + 1).reset_index(drop=True) if nbad else items.iloc[0:0].copy()
    for i in range(len(bad)):
        bad.loc[i, "order_id"] = f"BADITM{i:05d}"
        if i % 2 == 0: bad.loc[i, "price"] = "-10.00"
        else: bad.loc[i, "freight_value"] = "-1.00"
    n, nb = write_batches(out, "order_items", pd.concat([items, dup, bad], ignore_index=True), cols)
    record("order_items", items[cols], n, nb, injected_duplicates=len(dup), injected_bad_rows=len(bad))

    # ---------------- order_payments ----------------
    pay = read(inp, "order_payments"); cols = list(pay.columns)
    pay["_batch"] = pay["order_id"].map(pbatch)
    assert pay["_batch"].notna().all()
    dup = pay.sample(frac=0.01 if inject else 0, random_state=a.seed)
    bad = pay.sample(n=nbad, random_state=a.seed + 2).reset_index(drop=True) if nbad else pay.iloc[0:0].copy()
    for i in range(len(bad)):
        bad.loc[i, "order_id"] = f"BADPAY{i:05d}"
        if i % 2 == 0: bad.loc[i, "payment_value"] = "-5.00"
        else: bad.loc[i, "payment_type"] = "bitcoin"
    n, nb = write_batches(out, "order_payments", pd.concat([pay, dup, bad], ignore_index=True), cols)
    record("order_payments", pay[cols], n, nb, injected_duplicates=len(dup), injected_bad_rows=len(bad))

    # ---------------- order_reviews (arrive late: batch = review creation month) ----------------
    rev = read(inp, "order_reviews"); cols = list(rev.columns)
    rev["_batch"] = month_end(pd.to_datetime(rev["review_creation_date"], errors="coerce"))
    dropped = int(rev["_batch"].isna().sum()); rev = rev[rev["_batch"].notna()].copy()
    dup = rev.sample(frac=0.01 if inject else 0, random_state=a.seed)
    bad = rev.sample(n=nbad, random_state=a.seed + 3).reset_index(drop=True) if nbad else rev.iloc[0:0].copy()
    for i in range(len(bad)):
        bad.loc[i, "order_id"] = f"BADREV{i:05d}"; bad.loc[i, "review_score"] = "9"
    n, nb = write_batches(out, "order_reviews", pd.concat([rev, dup, bad], ignore_index=True), cols)
    record("order_reviews", rev[cols], n, nb, injected_duplicates=len(dup), injected_bad_rows=len(bad),
           rows_dropped_bad_date=dropped)

    # ---------------- reference tables: one full load ----------------
    for t in ["customers", "products", "sellers", "geolocation", "category_translation"]:
        df = read(inp, t); cols = list(df.columns)
        dup = df.sample(frac=0.005 if (inject and t == "customers") else 0, random_state=a.seed)
        full = pd.concat([df, dup], ignore_index=True); full["_batch"] = INITIAL_BATCH
        n, nb = write_batches(out, t, full, cols)
        record(t, df, n, nb, injected_duplicates=len(dup))

    (out / "manifest.json").write_text(json.dumps(man, indent=2))
    print(f"Done. Wrote batches + manifest to {out}")
    for t, m in man["tables"].items():
        print(f"  {t:22s} original={m['rows_original']:>8} bronze_rows={m['bronze_rows_written']:>8} "
              f"expected_silver={m['expected_silver_rows']:>8} batches={m['batches']}")


if __name__ == "__main__":
    main()
