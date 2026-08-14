# gcp-billing-export

BigQuery queries against the GCP billing export table
`prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_billing_export_resource_v1_0194CA_24F6D5_7ED48D`.

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
