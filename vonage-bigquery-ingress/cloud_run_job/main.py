"""Part 3 — Cloud Run Job: import Vonage Reports API data into BigQuery.

Flow, per (product, direction) pair: POST /v2/reports to request an async
report -> poll GET /v2/reports/{id} until SUCCESS -> download and unzip the
CSV from the download_report link -> transform each row -> load into a
staging table -> MERGE into the target table, keyed on (usage_date,
record_id) so re-running for the same window doesn't duplicate rows.

See ../README.md for the full design, including which parts of this are
confirmed against Vonage's docs (SMS CSV schema) versus unverified
placeholders (Voice/WebSocket CSV schema, dedup-key field name) that need
checking against a real report before this runs on a schedule.
"""

import csv
import datetime
import hashlib
import io
import json
import os
import time
import zipfile

import requests
from google.cloud import bigquery

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "prj-ufonia-cmn-lon-billing-01")
BQ_DATASET = os.environ.get("BQ_DATASET", "bq_dataset_vonage_cost_and_usage")
BQ_TABLE = os.environ.get("BQ_TABLE", "vonage_cost_and_usage")

VONAGE_ACCOUNT_ID = os.environ["VONAGE_ACCOUNT_ID"]
VONAGE_API_KEY = os.environ["VONAGE_API_KEY"]
VONAGE_API_SECRET = os.environ["VONAGE_API_SECRET"]
VONAGE_API_BASE = os.environ.get("VONAGE_API_BASE", "https://api.nexmo.com")

# Reports API takes one product per request (see ../README.md Part 1 for the
# full list of accepted values). Extend this list if the account bills for
# other products (VERIFY-API, NUMBER-INSIGHT, MESSAGES, ...).
VONAGE_PRODUCTS = os.environ.get("VONAGE_PRODUCTS", "SMS,VOICE-CALL,VOICE-TTS,WEBSOCKET-CALL").split(",")
DIRECTIONS = ["inbound", "outbound"]

# How many days back to request each run — covers same-day restatement
# without re-requesting the world every time.
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "2"))

POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300

# Maps a Reports API product to our dashboard category. VOICE-CALL splits by
# direction to match the existing Inbound Calls / Outbound Calls split from
# the manual traffic report; everything else not listed here is "Other".
PRODUCT_CATEGORY = {
    "SMS": "SMS",
    "WEBSOCKET-CALL": "WebSocket",
}

# Tried in order against each raw row to find a stable per-record ID.
# Confirmed present for SMS ("message_id"). Voice/WebSocket field names are
# unverified — see README.
RECORD_ID_FIELDS = ["message_id", "call_id", "uuid", "id"]

# Tried in order to find the row's usage date. Confirmed present for SMS
# ("date_received"). Falls back to the request's own date_start if none of
# these are present in the row.
DATE_FIELDS = ["date_received", "date_start_time", "date"]


def auth():
    return (VONAGE_API_KEY, VONAGE_API_SECRET)


def request_report(product, direction, date_start, date_end):
    resp = requests.post(
        f"{VONAGE_API_BASE}/v2/reports",
        auth=auth(),
        json={
            "product": product,
            "account_id": VONAGE_ACCOUNT_ID,
            "direction": direction,
            "date_start": date_start,
            "date_end": date_end,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def poll_report(request_id):
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = requests.get(f"{VONAGE_API_BASE}/v2/reports/{request_id}", auth=auth(), timeout=30)
        resp.raise_for_status()
        body = resp.json()
        status = body["request_status"]
        if status == "SUCCESS":
            return body
        if status in ("FAILED", "ABORTED", "TRUNCATED"):
            print(f"[{request_id}] report ended with status {status}, skipping")
            return None
        time.sleep(POLL_INTERVAL_SECONDS)
    print(f"[{request_id}] timed out waiting for report, skipping")
    return None


def download_report_rows(report):
    download_url = report["_links"]["download_report"]["href"]
    resp = requests.get(download_url, auth=auth(), timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(csv_name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8")
            return list(csv.DictReader(text))


def first_present(row, field_names):
    for name in field_names:
        value = row.get(name)
        if value:
            return value
    return None


def category_for(product, direction):
    if product in PRODUCT_CATEGORY:
        return PRODUCT_CATEGORY[product]
    if product == "VOICE-CALL":
        return "Inbound Calls" if direction == "inbound" else "Outbound Calls"
    return "Other"


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def transform_row(row, product, direction, fallback_date):
    record_id = first_present(row, RECORD_ID_FIELDS)
    if record_id is None:
        # No known ID field found — hash the row as a last resort. Not a
        # stable dedup key across restatements; see README caveat.
        record_id = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()

    usage_date_raw = first_present(row, DATE_FIELDS) or fallback_date
    usage_date = usage_date_raw[:10]

    return {
        "usage_date": usage_date,
        "record_id": record_id,
        "product": product,
        "direction": row.get("direction") or direction,
        "category": category_for(product, direction),
        "total_price": to_float(row.get("total_price")),
        "currency": row.get("currency"),
        "network": row.get("network"),
        "country": row.get("country"),
        "status": row.get("status"),
        "raw": json.dumps(row),
    }


SCHEMA = [
    bigquery.SchemaField("usage_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("record_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("product", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("direction", "STRING"),
    bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("total_price", "FLOAT64"),
    bigquery.SchemaField("currency", "STRING"),
    bigquery.SchemaField("network", "STRING"),
    bigquery.SchemaField("country", "STRING"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("raw", "JSON"),
]
FIELD_NAMES = [f.name for f in SCHEMA]


def load_staging_table(bq, staging_table_id, rows):
    job_config = bigquery.LoadJobConfig(
        schema=SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    )
    job = bq.load_table_from_json(rows, staging_table_id, job_config=job_config)
    job.result()
    return job.output_rows


def merge_into_target(bq, target_table_id, staging_table_id):
    update_clause = ",\n        ".join(
        f"{f} = S.{f}" for f in FIELD_NAMES if f not in ("usage_date", "record_id")
    )
    insert_cols = ", ".join(FIELD_NAMES)
    insert_vals = ", ".join(f"S.{f}" for f in FIELD_NAMES)
    sql = f"""
    MERGE `{target_table_id}` T
    USING `{staging_table_id}` S
    ON T.usage_date = S.usage_date AND T.record_id = S.record_id
    WHEN MATCHED THEN UPDATE SET
        {update_clause}
    WHEN NOT MATCHED THEN INSERT ({insert_cols})
    VALUES ({insert_vals})
    """
    bq.query(sql).result()


def run():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    date_start = (today - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat() + "T00:00:00Z"
    date_end = today.isoformat() + "T00:00:00Z"

    bq = bigquery.Client(project=GCP_PROJECT_ID)
    target_table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    staging_table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}_staging"

    for product in VONAGE_PRODUCTS:
        for direction in DIRECTIONS:
            requested = request_report(product, direction, date_start, date_end)
            report = poll_report(requested["request_id"])
            if report is None:
                continue

            raw_rows = download_report_rows(report)
            if not raw_rows:
                print(f"[{product}/{direction}] 0 rows, skipping load")
                continue

            rows = [transform_row(r, product, direction, date_start) for r in raw_rows]
            loaded = load_staging_table(bq, staging_table_id, rows)
            merge_into_target(bq, target_table_id, staging_table_id)
            print(f"[{product}/{direction}] {loaded} rows staged and merged into {target_table_id}")


if __name__ == "__main__":
    run()
