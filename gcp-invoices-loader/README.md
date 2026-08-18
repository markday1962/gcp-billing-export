# GCP Manual Invoice Loader

Fills the gap the live BigQuery billing export can't: **GCP's billing export to BigQuery only contains data from the day it was enabled onward** (2026-08-01 for `bq_dataset_billing_ufonia_invoice`) — Google does not backfill historical usage into it, and there's no API to pull historical detailed cost data the way AWS's CUR files or Vonage's Reports API allow. For any month before that, the only source is the per-service summary invoice you can download from the Cloud Console.

## How to get an invoice CSV

Google Cloud Console → **Billing → Reports** → set the date range to the month you want → **Download CSV**. Drop the file straight into this folder — don't rename it, the loader parses the billing period out of the filename.

Expected filename shape: `Ufonia GCP Invoice Account_Reports, YYYY-MM-DD — YYYY-MM-DD.csv` (the first date is what matters; the loader takes its year/month and ignores the rest).

## What's in the CSV

One row per service for the month, **not** line-item/resource detail:
`Service description, Service ID, List cost, Negotiated savings, Savings programmes, Other savings, Unrounded subtotal, Subtotal, Percent change vs previous period` — plus a `Subtotal`/`Tax`/`Filtered total` footer with no Service ID (the loader skips those rows; the per-service `subtotal` column already sums to the same total).

This is coarser than the live export (no project, no SKU, no resource, no usage amount) — it's enough to know what a past month cost per service, not enough to reproduce `platformcogs.sql`/`apicogs.sql`-style per-project breakdowns for that month.

## Loading into BigQuery

```sh
python3 -m venv venv
venv/bin/pip install google-cloud-bigquery
venv/bin/python load_invoice.py                 # loads every *.csv in this folder
venv/bin/python load_invoice.py "some-file.csv" # or just one
```

Lands in `prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_monthly_invoice_summary`, `MERGE`d on `(invoice_month, service_id)` — safe to re-run, and safe to re-run after re-downloading a month (e.g. once savings/credits are finalized).

**Why the Python client and not `bq load`:** this org's VPC Service Controls policy blocks `bq load`'s local-file upload path outright. `google-cloud-bigquery`'s `load_table_from_json` isn't affected — use that.

## Status

Loaded so far: **April, May, June, July 2026** (30–33 service rows each, totals $44.5k–$52.3k). August onward comes from the live export instead — don't double-load a month that's already covered there.
