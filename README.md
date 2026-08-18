# gcp-billing-export

BigQuery queries against the GCP billing export table
`prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_billing_export_resource_v1_0194CA_24F6D5_7ED48D`,
plus an AWS query against a CUR-to-BigQuery import table for the AWS side of
spend (see `aws-bigquery-loader/README.md` for that pipeline).

## Queries

### `bigquery-sql/services.sql`

Cost broken down by service (`service.description`) for the current calendar
month, with columns: Cost, Negotiated savings, Savings programmes, Other
savings, Subtotal. Sorted by `Subtotal DESC` and capped at `LIMIT 10` — top
10 services by spend, not the full list.

### `bigquery-sql/platformcogs.sql`

Same shape as `services.sql`, scoped to the wider set of projects/services
that make up platform (non-API) COGS — 8 projects, 25 service IDs. Also
sorted `Subtotal DESC` and capped at `LIMIT 10`.

### `bigquery-sql/apicogs.sql`

Same shape as `services.sql`, scoped to specific projects and services (COGS
for API-based services):

- Projects: `prj-ufonia-prd-lon-svc-01` (870453169286), `prj-ufonia-prd-lon-host-01` (1025855247143)
- Services: `63DE-82AB-F564` (Cloud Speech API), `02DA-B362-D983` (unresolved — see Known issues)

### `bigquery-sql/aws_services.sql`

Cost by service for the current calendar month (Europe/London, matching
`services.sql`'s window), for AWS account `453829601976`. Sourced from
`bg_dataset_aws_cost_and_usage.aws_cost_and_usage`, a BigQuery table
populated daily by a separate CUR-to-BigQuery import pipeline — see
`aws-bigquery-loader/README.md` for the full design (AWS Data Export → keyless OIDC
federation → Cloud Run Job → BigQuery). Excludes `line_item_type = 'Tax'`,
to match the GCP queries' exclusion of tax rows. Sorted by `Cost DESC` and
capped at `LIMIT 10`, same shape as `services.sql`.

For the previous calendar month instead of the current one, see
`bigquery-sql/aws_monthly_cost.sql` — same `CURRENT_DATE`-relative pattern,
shifted back one month, so it always reflects "last month" without editing.

Note the underlying table only has data from when the CUR export started
(2026-08-01) onward — querying an earlier month returns zero rows until
AWS backfills further back or enough time passes.

**Not yet at parity with the GCP queries:** this only surfaces
`UnblendedCost` (a single number per service), not the
Cost / Negotiated savings / Savings programmes / Other savings breakdown the
GCP queries have. Getting the equivalent breakdown would mean also loading
`reservation`/`savingsPlan` effective-cost fields from CUR (present in the
BigQuery schema already, just not used in this query yet) — left for a
follow-up.

This replaced an earlier AWS Cost Explorer script (`aws/services.sh`,
account `102369858221`) that was removed once this pipeline reached
parity for the dashboard's needs.

### `vonage-bigquery-ingress/`

Manually-dropped Vonage/Nexmo invoice CSVs (traffic reports), not a live
query — add a new invoice file here when one arrives. Each file has one row
per usage line item, with columns including `Product_Group`, `SKU`, `Usage`
(cost), and `Currency` (typically EUR).

For a cost-by-category breakdown of an invoice, categorize by `SKU`:

- **SMS** — `Inbound SMS`, `Outbound SMS`
- **Inbound Calls** — `VAPI - Inbound`
- **Outbound Calls** — `VAPI - Outbound`
- **WebSocket** — `WebSocket` (voice media streaming) — kept as its own
  category rather than folded into Inbound/Outbound Calls or lumped into
  "Other", per how this was categorized for `INV00182587`
- **Other** — everything else (number rentals, `IP Calls`, `Standard TTS`)

Each invoice is a single EUR figure for whatever usage period it covers
(e.g. `INV00182587` is a single day, 2026-06-01) — not a month-to-date
figure and not USD, so it doesn't belong in the GCP/AWS summary table;
show it as its own dashboard section instead.

## Changes from the original console-generated queries

All three queries were originally exported as-is from the GCP Billing
Console's query builder, which leaves several placeholders and a hardcoded
date range. Cleanup applied to all three:

- **Parameterized the date range.** Replaced the hardcoded `usage_start_time`
  bounds (e.g. `'2026-08-01T00:00:00 US/Pacific'`) with a rolling
  current-calendar-month window based on `CURRENT_DATE('Europe/London')`, so
  the query always reflects the current month without manual edits. All
  three queries currently use the current month. `apicogs.sql` and
  `platformcogs.sql` are intended to run a month in arrears (previous
  calendar month) once a full prior month's data exists in the export
  table — right now the table only contains data from 2026-08-01 onward, so
  a previous-month window returns nothing. To switch them to previous-month,
  change the bounds to:
  `usage_start_time >= TIMESTAMP(DATE_TRUNC(DATE_SUB(CURRENT_DATE('Europe/London'), INTERVAL 1 MONTH), MONTH), 'Europe/London')`
  and
  `usage_start_time < TIMESTAMP(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), 'Europe/London')`.
- **Switched timezone from `US/Pacific` to `Europe/London`.**
- **Removed the vestigial `spend_cud_fee_skus` CTE.** It was an empty SKU
  list (`UNNEST([''])`) left over from the console template, meaning
  `spend_cud_fee_cost` always evaluated to `0` via an `IN` subquery that could
  never match. Replaced with a literal `0 AS spend_cud_fee_cost`. If CUD
  (Committed Use Discount) commitment fee SKUs need to be excluded in future,
  this is where to reintroduce them.
- **Removed the trailing `- 0`** in the `Subtotal` calculation (harmless but
  vestigial console boilerplate).

Additional fixes specific to `apicogs.sql` and `platformcogs.sql`:

- **Filled in the credit-type lists.** `cud_credits` and `other_savings` were
  computed from `c.type IN ('')` (an empty placeholder, always `0`). Replaced
  with the same real credit-type lists used in `services.sql` (e.g.
  `COMMITTED_USAGE_DISCOUNT`, `PROMOTION`, `FREE_TIER`, etc.), so these
  columns now actually compute instead of always returning zero.
- **Fixed the `service.id` filter format.** The filters were written as
  `service.id IN ('services/63DE-82AB-F564', ...)`, but the export table
  stores `service.id` as a bare code (e.g. `63DE-82AB-F564`), not prefixed
  with `services/`. The prefix meant the filter never matched anything and
  the query silently returned zero (`apicogs.sql`) or far fewer
  (`platformcogs.sql`) rows than it should. Removed the `services/` prefix
  from every ID in both queries.

## Known issues

- **`platformcogs.sql` previously had 4 `service.id` filter values that
  didn't match any service in this billing export** — `9B82-7513-9D1C`,
  `C5E6-A27F-6A44`, `FBF2-FC68-171A`, `1DB1-3CD3-35A3`. Checked against the
  full distinct list of 39 `service.id` values present in the export table
  (with and without the `services/` prefix) — no match. Since they matched
  zero rows, removing them from the filter has no effect on totals; they
  were dropped to keep the query honest about what it's actually scoping.
  If platform COGS coverage for those services is needed, the correct IDs
  still need to be found and re-added.
- **`apicogs.sql`: `02DA-B362-D983` does not match any service in this
  billing export.** Same check as above — no match. Either this service has
  never had usage on this billing account, or it's the wrong ID for whatever
  second API `apicogs.sql` was meant to cover. Needs the correct service ID
  before this query's totals can be considered complete.
