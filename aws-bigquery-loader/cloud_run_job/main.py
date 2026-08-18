"""Part 4 — Cloud Run Job: import AWS CUR (Cost and Usage Report) data into BigQuery.

Flow: mint a Google ID token for this job's service account -> exchange it
for short-lived AWS credentials via AssumeRoleWithWebIdentity -> read the
CUR "current" manifest for each billing period being watched -> download and
parse the referenced CSV.gz file(s) -> load into a staging table -> MERGE
into the target table, keyed on (usage_date, line_item_id) so a restated day
cleanly replaces the prior version instead of duplicating rows.

See ../README.md for the full design.
"""

import csv
import datetime
import gzip
import io
import json
import os

import boto3
import google.auth.transport.requests
import google.oauth2.id_token
from google.cloud import bigquery

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "prj-ufonia-cmn-lon-billing-01")
BQ_DATASET = os.environ.get("BQ_DATASET", "bg_dataset_aws_cost_and_usage")
BQ_TABLE = os.environ.get("BQ_TABLE", "aws_cost_and_usage")
GCP_SA_EMAIL = os.environ.get(
    "GCP_SA_EMAIL", "cur-importer@prj-ufonia-cmn-lon-billing-01.iam.gserviceaccount.com"
)

AWS_ROLE_ARN = os.environ.get(
    "AWS_ROLE_ARN", "arn:aws:iam::453829601976:role/cur-bigquery-import-role"
)
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
CUR_BUCKET = os.environ.get("CUR_BUCKET", "cost-by-environment")
CUR_S3_PREFIX = os.environ.get("CUR_S3_PREFIX", "cost-by-environment")
CUR_REPORT_NAME = os.environ.get("CUR_REPORT_NAME", "cost-by-environment")

# How many days into a new month to keep re-checking the previous month's
# manifest, to catch AWS's restatement of the prior billing period.
RESTATEMENT_WINDOW_DAYS = 7

# (raw CUR column name, target BigQuery column name, value transform, BigQuery type)
COLUMNS = [
    ("bill/PayerAccountId", "bill_payer_account_id", "str", "STRING"),
    ("bill/BillingPeriodStartDate", "bill_billing_period_start_date", "date", "DATE"),
    ("lineItem/UsageAccountId", "line_item_usage_account_id", "str", "STRING"),
    ("lineItem/LineItemType", "line_item_type", "str", "STRING"),
    ("lineItem/UsageStartDate", "line_item_usage_start_date", "str", "TIMESTAMP"),
    ("lineItem/UsageEndDate", "line_item_usage_end_date", "str", "TIMESTAMP"),
    ("lineItem/ProductCode", "line_item_product_code", "str", "STRING"),
    ("lineItem/UsageType", "line_item_usage_type", "str", "STRING"),
    ("lineItem/Operation", "line_item_operation", "str", "STRING"),
    ("lineItem/LineItemDescription", "line_item_description", "str", "STRING"),
    ("lineItem/UsageAmount", "line_item_usage_amount", "float", "FLOAT64"),
    ("lineItem/UnblendedRate", "line_item_unblended_rate", "float", "FLOAT64"),
    ("lineItem/UnblendedCost", "line_item_unblended_cost", "float", "FLOAT64"),
    ("product/ProductName", "product_name", "str", "STRING"),
    ("product/servicecode", "product_service_code", "str", "STRING"),
    ("product/region", "product_region", "str", "STRING"),
    ("pricing/unit", "pricing_unit", "str", "STRING"),
    ("reservation/EffectiveCost", "reservation_effective_cost", "float", "FLOAT64"),
    ("savingsPlan/SavingsPlanEffectiveCost", "savings_plan_effective_cost", "float", "FLOAT64"),
    ("resourceTags/user:environment", "resource_tags_environment", "str", "STRING"),
    (
        "resourceTags/user:transfer:customHostname",
        "resource_tags_transfer_custom_hostname",
        "str",
        "STRING",
    ),
    ("costCategory/Development", "cost_category_development", "str", "STRING"),
    ("costCategory/Production", "cost_category_production", "str", "STRING"),
]

SCHEMA = [
    bigquery.SchemaField("usage_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("line_item_id", "STRING", mode="REQUIRED"),
] + [bigquery.SchemaField(target, bq_type) for _, target, _, bq_type in COLUMNS]
FIELD_NAMES = [f.name for f in SCHEMA]


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def to_str(value):
    return value if value not in (None, "") else None


def to_date(value):
    return value[:10] if value else None


TRANSFORMS = {"str": to_str, "float": to_float, "date": to_date}


def billing_period_label(day):
    start = day.replace(day=1)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return f"{start:%Y%m%d}-{end:%Y%m%d}"


def billing_periods_to_check(today):
    periods = [billing_period_label(today)]
    if today.day <= RESTATEMENT_WINDOW_DAYS:
        last_of_prev_month = today.replace(day=1) - datetime.timedelta(days=1)
        periods.append(billing_period_label(last_of_prev_month))
    return periods


def get_google_id_token(audience):
    request = google.auth.transport.requests.Request()
    return google.oauth2.id_token.fetch_id_token(request, audience)


def assume_aws_role(id_token):
    sts = boto3.client("sts", region_name=AWS_REGION)
    resp = sts.assume_role_with_web_identity(
        RoleArn=AWS_ROLE_ARN,
        RoleSessionName="cur-import",
        WebIdentityToken=id_token,
        DurationSeconds=3600,
    )
    return resp["Credentials"]


def s3_client(aws_credentials):
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=aws_credentials["AccessKeyId"],
        aws_secret_access_key=aws_credentials["SecretAccessKey"],
        aws_session_token=aws_credentials["SessionToken"],
    )


def read_json_object(s3, bucket, key):
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return json.loads(body)


def transform_row(row):
    out = {
        "usage_date": to_date(row.get("lineItem/UsageStartDate")),
        "line_item_id": row.get("identity/LineItemId"),
    }
    for raw_col, target, kind, _ in COLUMNS:
        out[target] = TRANSFORMS[kind](row.get(raw_col))
    return out


def load_report_rows(s3, bucket, report_key):
    gz_bytes = s3.get_object(Bucket=bucket, Key=report_key)["Body"].read()
    text = io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(gz_bytes)), encoding="utf-8")
    return [transform_row(row) for row in csv.DictReader(text)]


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
        f"{f} = S.{f}" for f in FIELD_NAMES if f not in ("usage_date", "line_item_id")
    )
    insert_cols = ", ".join(FIELD_NAMES)
    insert_vals = ", ".join(f"S.{f}" for f in FIELD_NAMES)
    sql = f"""
    MERGE `{target_table_id}` T
    USING `{staging_table_id}` S
    ON T.usage_date = S.usage_date AND T.line_item_id = S.line_item_id
    WHEN MATCHED THEN UPDATE SET
        {update_clause}
    WHEN NOT MATCHED THEN INSERT ({insert_cols})
    VALUES ({insert_vals})
    """
    bq.query(sql).result()


def run():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    periods = billing_periods_to_check(today)

    id_token = get_google_id_token(GCP_SA_EMAIL)
    aws_credentials = assume_aws_role(id_token)
    s3 = s3_client(aws_credentials)
    bq = bigquery.Client(project=GCP_PROJECT_ID)

    target_table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    staging_table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}_staging"

    for period in periods:
        manifest_key = f"{CUR_S3_PREFIX}/{CUR_REPORT_NAME}/{period}/{CUR_REPORT_NAME}-Manifest.json"
        try:
            manifest = read_json_object(s3, CUR_BUCKET, manifest_key)
        except s3.exceptions.NoSuchKey:
            print(f"[{period}] no manifest yet at s3://{CUR_BUCKET}/{manifest_key}, skipping")
            continue

        rows = []
        for report_key in manifest["reportKeys"]:
            rows.extend(load_report_rows(s3, CUR_BUCKET, report_key))

        if not rows:
            print(f"[{period}] manifest present but no rows, skipping load")
            continue

        loaded = load_staging_table(bq, staging_table_id, rows)
        merge_into_target(bq, target_table_id, staging_table_id)
        print(
            f"[{period}] assembly {manifest.get('assemblyId')}: "
            f"{loaded} rows staged and merged into {target_table_id}"
        )


if __name__ == "__main__":
    run()
