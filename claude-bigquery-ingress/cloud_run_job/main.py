"""Part 3 — Cloud Run Job: import Anthropic Usage & Cost Admin API data into
BigQuery.

Flow, per endpoint (usage, cost): GET a rolling LOOKBACK_DAYS-day window,
paging through has_more/next_page -> flatten each time bucket's `results`
into rows -> load into a staging table -> MERGE into the target table,
keyed on a hash of usage_date + every dimension field (these are
pre-aggregated rows from the API, not individual events, so there's no
natural unique ID to dedup on).

See ../README.md for the full design, including the confirmed exact
request/response shapes (verified against Anthropic's docs, not guessed)
and the one open item: whether `amount` in the cost report is dollars or
cents — this pipeline stores it as-is and flags it for verification once a
real Admin API key exists.
"""

import datetime
import hashlib
import json
import os

import requests
from google.cloud import bigquery

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "prj-ufonia-cmn-lon-billing-01")
BQ_DATASET = os.environ.get("BQ_DATASET", "bq_dataset_claude_cost_and_usage")
BQ_USAGE_TABLE = os.environ.get("BQ_USAGE_TABLE", "claude_usage")
BQ_COST_TABLE = os.environ.get("BQ_COST_TABLE", "claude_cost")

ANTHROPIC_ADMIN_KEY = os.environ["ANTHROPIC_ADMIN_KEY"]
ANTHROPIC_API_BASE = os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com")
ANTHROPIC_VERSION = "2023-06-01"

# How many days back to request each run — catches late-finalized cost
# corrections without re-pulling the world every time.
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "4"))

USAGE_GROUP_BY = ["model", "workspace_id"]
COST_GROUP_BY = ["workspace_id", "description"]

USAGE_DIMENSION_FIELDS = [
    "account_id",
    "api_key_id",
    "workspace_id",
    "service_account_id",
    "model",
    "service_tier",
    "context_window",
    "inference_geo",
]

COST_DIMENSION_FIELDS = [
    "workspace_id",
    "description",
    "cost_type",
    "token_type",
    "model",
    "service_tier",
    "context_window",
    "inference_geo",
]


def headers():
    return {
        "x-api-key": ANTHROPIC_ADMIN_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
    }


def paginate(path, params):
    """Yields every bucket across all pages for a usage/cost report endpoint."""
    page = None
    while True:
        query = dict(params)
        if page:
            query["page"] = page
        resp = requests.get(f"{ANTHROPIC_API_BASE}{path}", headers=headers(), params=query, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        yield from body["data"]
        if not body.get("has_more"):
            return
        page = body["next_page"]


def record_id(usage_date, dimension_values):
    key = usage_date + "|" + "|".join(str(v) for v in dimension_values)
    return hashlib.sha256(key.encode()).hexdigest()


def transform_usage_bucket(bucket):
    usage_date = bucket["starting_at"][:10]
    rows = []
    for result in bucket["results"]:
        cache_creation = result.get("cache_creation") or {}
        server_tool_use = result.get("server_tool_use") or {}
        dims = [result.get(f) for f in USAGE_DIMENSION_FIELDS]
        rows.append(
            {
                "usage_date": usage_date,
                "record_id": record_id(usage_date, dims),
                "bucket_start": bucket["starting_at"],
                "bucket_end": bucket["ending_at"],
                "account_id": result.get("account_id"),
                "api_key_id": result.get("api_key_id"),
                "workspace_id": result.get("workspace_id"),
                "service_account_id": result.get("service_account_id"),
                "model": result.get("model"),
                "service_tier": result.get("service_tier"),
                "context_window": result.get("context_window"),
                "inference_geo": result.get("inference_geo"),
                "uncached_input_tokens": result.get("uncached_input_tokens"),
                "cache_read_input_tokens": result.get("cache_read_input_tokens"),
                "cache_creation_ephemeral_5m_input_tokens": cache_creation.get("ephemeral_5m_input_tokens"),
                "cache_creation_ephemeral_1h_input_tokens": cache_creation.get("ephemeral_1h_input_tokens"),
                "output_tokens": result.get("output_tokens"),
                "web_search_requests": server_tool_use.get("web_search_requests"),
            }
        )
    return rows


def transform_cost_bucket(bucket):
    usage_date = bucket["starting_at"][:10]
    rows = []
    for result in bucket["results"]:
        dims = [result.get(f) for f in COST_DIMENSION_FIELDS]
        amount = result.get("amount")
        rows.append(
            {
                "usage_date": usage_date,
                "record_id": record_id(usage_date, dims),
                "bucket_start": bucket["starting_at"],
                "bucket_end": bucket["ending_at"],
                "workspace_id": result.get("workspace_id"),
                "description": result.get("description"),
                "cost_type": result.get("cost_type"),
                "token_type": result.get("token_type"),
                "model": result.get("model"),
                "service_tier": result.get("service_tier"),
                "context_window": result.get("context_window"),
                "inference_geo": result.get("inference_geo"),
                "currency": result.get("currency"),
                "amount_usd": float(amount) if amount is not None else None,
            }
        )
    return rows


USAGE_SCHEMA = [
    bigquery.SchemaField("usage_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("record_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("bucket_start", "TIMESTAMP"),
    bigquery.SchemaField("bucket_end", "TIMESTAMP"),
    bigquery.SchemaField("account_id", "STRING"),
    bigquery.SchemaField("api_key_id", "STRING"),
    bigquery.SchemaField("workspace_id", "STRING"),
    bigquery.SchemaField("service_account_id", "STRING"),
    bigquery.SchemaField("model", "STRING"),
    bigquery.SchemaField("service_tier", "STRING"),
    bigquery.SchemaField("context_window", "STRING"),
    bigquery.SchemaField("inference_geo", "STRING"),
    bigquery.SchemaField("uncached_input_tokens", "INT64"),
    bigquery.SchemaField("cache_read_input_tokens", "INT64"),
    bigquery.SchemaField("cache_creation_ephemeral_5m_input_tokens", "INT64"),
    bigquery.SchemaField("cache_creation_ephemeral_1h_input_tokens", "INT64"),
    bigquery.SchemaField("output_tokens", "INT64"),
    bigquery.SchemaField("web_search_requests", "INT64"),
]

COST_SCHEMA = [
    bigquery.SchemaField("usage_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("record_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("bucket_start", "TIMESTAMP"),
    bigquery.SchemaField("bucket_end", "TIMESTAMP"),
    bigquery.SchemaField("workspace_id", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("cost_type", "STRING"),
    bigquery.SchemaField("token_type", "STRING"),
    bigquery.SchemaField("model", "STRING"),
    bigquery.SchemaField("service_tier", "STRING"),
    bigquery.SchemaField("context_window", "STRING"),
    bigquery.SchemaField("inference_geo", "STRING"),
    bigquery.SchemaField("currency", "STRING"),
    bigquery.SchemaField("amount_usd", "FLOAT64"),
]


def load_and_merge(bq, target_table_id, schema, rows):
    if not rows:
        print(f"{target_table_id}: 0 rows, skipping load")
        return

    staging_table_id = f"{target_table_id}_staging"
    field_names = [f.name for f in schema]

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    )
    job = bq.load_table_from_json(rows, staging_table_id, job_config=job_config)
    job.result()

    update_clause = ",\n        ".join(
        f"{f} = S.{f}" for f in field_names if f not in ("usage_date", "record_id")
    )
    insert_cols = ", ".join(field_names)
    insert_vals = ", ".join(f"S.{f}" for f in field_names)
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
    print(f"{target_table_id}: {job.output_rows} rows staged and merged")


def run():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    starting_at = (today - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat() + "T00:00:00Z"
    ending_at = today.isoformat() + "T00:00:00Z"

    bq = bigquery.Client(project=GCP_PROJECT_ID)
    usage_table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_USAGE_TABLE}"
    cost_table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_COST_TABLE}"

    usage_rows = []
    for bucket in paginate(
        "/v1/organizations/usage_report/messages",
        {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "bucket_width": "1d",
            "group_by[]": USAGE_GROUP_BY,
        },
    ):
        usage_rows.extend(transform_usage_bucket(bucket))
    load_and_merge(bq, usage_table_id, USAGE_SCHEMA, usage_rows)

    cost_rows = []
    for bucket in paginate(
        "/v1/organizations/cost_report",
        {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "group_by[]": COST_GROUP_BY,
        },
    ):
        cost_rows.extend(transform_cost_bucket(bucket))
    load_and_merge(bq, cost_table_id, COST_SCHEMA, cost_rows)


if __name__ == "__main__":
    run()
