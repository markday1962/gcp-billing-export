# gcp-billing-export

BigQuery queries against the GCP billing export table
`prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_billing_export_resource_v1_0194CA_24F6D5_7ED48D`,
plus an AWS Cost Explorer query for the AWS side of spend.

## Queries

### `bigquery/services.sql`

Cost broken down by service (`service.description`) for the current calendar
month, with columns: Cost, Negotiated savings, Savings programmes, Other
savings, Subtotal. Sorted by `Subtotal DESC` and capped at `LIMIT 10` — top
10 services by spend, not the full list.

### `bigquery/platformcogs.sql`

Same shape as `services.sql`, scoped to the wider set of projects/services
that make up platform (non-API) COGS — 8 projects, 25 service IDs. Also
sorted `Subtotal DESC` and capped at `LIMIT 10`.

### `bigquery/apicogs.sql`

Same shape as `services.sql`, scoped to specific projects and services (COGS
for API-based services):

- Projects: `prj-ufonia-prd-lon-svc-01` (870453169286), `prj-ufonia-prd-lon-host-01` (1025855247143)
- Services: `63DE-82AB-F564` (Cloud Speech API), `02DA-B362-D983` (unresolved — see Known issues)

### `aws/services.sh`

Cost by service for the current calendar month to date (UTC), via the AWS
Cost Explorer API (`aws ce get-cost-and-usage`), for AWS account
`102369858221` (profile `AdministratorAccess-102369858221`). Excludes
`RECORD_TYPE = "Tax"`, to match the GCP queries' exclusion of tax rows.

Usage: `aws/services.sh [profile]` prints the raw Cost Explorer JSON
response to stdout (grouped by `SERVICE`, metric `UnblendedCost`) — shape it
with `jq` downstream, e.g. top 10 by cost descending:

```sh
aws/services.sh | jq -r '
  .ResultsByTime[0].Groups
  | map({service: .Keys[0], cost: (.Metrics.UnblendedCost.Amount | tonumber)})
  | sort_by(-.cost)
  | .[0:10][]
'
```

or the unlimited month-to-date total across every service:

```sh
aws/services.sh | jq '[.ResultsByTime[0].Groups[].Metrics.UnblendedCost.Amount | tonumber] | add'
```

Requires an active AWS SSO session for the profile
(`aws sso login --profile AdministratorAccess-102369858221`) — tokens expire
and need re-running periodically.

**Not yet at parity with the GCP queries:** this only surfaces
`UnblendedCost` (a single number per service), not the
Cost / Negotiated savings / Savings programmes / Other savings breakdown the
GCP queries have. Getting the equivalent breakdown out of Cost Explorer
would mean also pulling `NetUnblendedCost` (list-price vs. negotiated/RI/SP
discounts) and a `RECORD_TYPE = "Credit"` breakout — left for a follow-up.
Cost Explorer was chosen as the first pass for speed (no new infra); a CUR
export into BigQuery remains the option for full parity with the GCP query
shape if that's wanted later.

### `vonage/`

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
