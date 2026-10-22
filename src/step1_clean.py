"""
Step 1 - Clean the Online Retail II order lines.
Inputs : data/raw/online_retail_II.xlsx      (UCI dataset 502, 2 sheets)
         data/raw/non_product_codes.csv      (stock codes that are fees, postage, adjustments...)
Outputs: data/processed/order_lines.parquet  (one row per shipped product line)
         outputs/01_cleaning_log.csv         (rows removed at each rule)
Needs  : pip install pandas openpyxl pyarrow
Runtime: ~1-2 min (reading the Excel file is the slow part)
"""
from pathlib import Path
import pandas as pd

# --- Block 1: paths ------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs"
PROC.mkdir(parents=True, exist_ok=True)
OUT.mkdir(exist_ok=True)

# --- Block 2: read both sheets -------------------------------------------
# Invoice and StockCode stay text ("C489449", "85123A")
print("Reading Excel (1-2 min)...")
sheets = pd.read_excel(RAW / "online_retail_II.xlsx", sheet_name=None,
                       dtype={"Invoice": str, "StockCode": str})
s1, s2 = sheets["Year 2009-2010"], sheets["Year 2010-2011"]
log = [("Raw rows (both sheets)", len(s1) + len(s2))]

# The sheets overlap (1-9 Dec 2010 is in both): keep sheet 2's copy
s1 = s1[~s1.Invoice.isin(set(s2.Invoice))]
df = pd.concat([s1, s2], ignore_index=True)
df.columns = ["invoice", "stock_code", "description", "quantity", "invoice_date",
              "price", "customer_id", "country"]
log.append(("Remove 1-9 Dec 2010 rows repeated in both sheets", len(df)))


# --- Block 3: cleaning rules, in order -----------------------------------
def apply(rule, keep):
    global df
    df = df[keep].copy()
    log.append((rule, len(df)))


apply("Remove exact duplicate rows", ~df.duplicated())
apply("Remove cancellations (invoice starts with C)", ~df.invoice.str.startswith("C"))
apply("Remove bad-debt adjustments (invoice starts with A)", ~df.invoice.str.startswith("A"))

npc = pd.read_csv(RAW / "non_product_codes.csv")
exact = set(npc.stock_code[~npc.stock_code.str.endswith("*")])
prefixes = tuple(npc.stock_code[npc.stock_code.str.endswith("*")].str.rstrip("*"))
apply("Remove non-product codes (postage, fees, vouchers, tests)",
      ~(df.stock_code.isin(exact) | df.stock_code.str.startswith(prefixes)))
apply("Remove quantity <= 0 (stock write-offs, damages)", df.quantity > 0)
apply("Remove price <= 0 (no sale)", df.price > 0)

# --- Block 4: tidy and save ----------------------------------------------
df["customer_id"] = df.customer_id.astype("Int64")
df["line_value"] = (df.quantity * df.price).round(2)
df = df.sort_values("invoice_date").reset_index(drop=True)
df.to_parquet(PROC / "order_lines.parquet", index=False)

log = pd.DataFrame(log, columns=["step", "rows_after"])
log["rows_removed"] = (-log.rows_after.diff()).fillna(0).astype(int)
log.to_csv(OUT / "01_cleaning_log.csv", index=False)
print(log.to_string(index=False))
print(f"\nKept {len(df):,} product lines, {df.invoice.nunique():,} orders, "
      f"{df.stock_code.nunique():,} products, {df.invoice_date.min():%d %b %Y} - {df.invoice_date.max():%d %b %Y}")
print("Saved data/processed/order_lines.parquet and outputs/01_cleaning_log.csv")