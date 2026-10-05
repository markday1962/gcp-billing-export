# gcp-billing-export

BigQuery queries against the GCP billing export table
`prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_billing_export_resource_v1_0194CA_24F6D5_7ED48D`,
plus an AWS query against a CUR-to-BigQuery import table (see
`aws-bigquery-loader/README.md`) and a Vonage query against a Reports
API-to-BigQuery import table (see `vonage-bigquery-loader/README.md`) for
the non-GCP sides of spend.

## Queries

### `bigquery-sql/gcp_invoice.sql`

Reproduces the monthly Google Cloud invoice for the current invoice month
(September 2026: $40,424.12). It differs from `gcp_all_services.sql` in three
ways, all matching how Google builds the invoice: it groups by
`invoice.month` rather than usage time (so late-reported usage from the end
of the previous month is included), keeps every `cost_type` (tax,
adjustments and rounding included), and splits by `seller_name`. Only
seller `Google` is on Google's invoice; Marketplace sellers such as 84codes
AB (CloudAMQP) and Elasticsearch B.V. (Elastic Cloud) bill through the same
billing account but invoice separately. Added 2026-10-05.

### `bigquery-sql/gcp_all_services.sql`

Cost broken down by service (`service.description`) for the current calendar
month, with columns: Cost, Negotiated savings, Savings programmes, Other
savings, Subtotal. Sorted by `Subtotal DESC` and capped at `LIMIT 10` — top
10 services by spend, not the full list.

### `bigquery-sql/gcp_all_production.sql`

Same shape and same 24 platform service IDs as `gcp_uk_platform_cogs.sql`,
scoped to all 8 production projects: `prj-ufonia-prd-lon-svc-01`,
`prj-ufonia-prd-lon-svc-02`, `prj-ufonia-prd-lon-host-01`,
`prj-ufonia-prd-lon-orbit-01`, `prj-ufonia-prd-lon-ds-01`,
`prj-ufonia-prd-iowa-svc-01`, `prj-ufonia-prd-iowa-svc-02`,
`prj-ufonia-prd-iowa-host-01`. A superset of the UK and US Platform COGS
queries. Added 2026-10-05 from a Billing console export; the console version
also listed the 5 IDs removed from Platform COGS in August, which had no
usage in these projects. September 2026: Cost $17,026.39 (23 services).
Sorted `Subtotal DESC` and capped at `LIMIT 10`.

### `bigquery-sql/gcp_all_development.sql`

Same shape as `gcp_all_services.sql` (every service, no `service.id`
filter), scoped to the 4 development projects: `prj-ufonia-dev-lon-svc-01`,
`prj-ufonia-dev-host-01`, `prj-ufonia-dev-iowa-svc-02` ("Dora Advanced
Development") and `prj-ufonia-dev-iowa-host-01`. Includes everything the UK
R&D COGS queries cover. Note the asymmetry with `gcp_all_production.sql`,
which is limited to the 24 platform service IDs. Added 2026-10-05 from a
Billing console export (whose credit lists were already filled in).
September 2026: Cost $8,139.41 (39 services). Sorted `Subtotal DESC` and
capped at `LIMIT 10`.

### `bigquery-sql/gcp_uk_platform_cogs.sql`

Renamed from `gcp_platform_cogs.sql` on 2026-10-05, to distinguish it from
`gcp_us_platform_cogs.sql`; shown as "UK ..." in the billing dashboard.

Same shape as `gcp_all_services.sql`, scoped to the production projects and
24 platform (non-API) service IDs that make up platform COGS:

- Projects: `prj-ufonia-prd-lon-svc-01` (870453169286), `prj-ufonia-prd-lon-host-01` (1025855247143) — the same two production projects as `gcp_uk_api_cogs.sql`, just with a broader service list.

Sorted `Subtotal DESC` and capped at `LIMIT 10`.

**Corrected 2026-09-01:** this query previously scoped to a different set of
8 dev/staging/trial projects (`prj-ufonia-dev-iowa-svc-02`,
`prj-ufonia-dev-host-01`, `prj-ufonia-dev-iowa-host-01`,
`prj-ufonia-dev-lon-svc-01`, `prj-ufonia-stg-host-01`,
`prj-ufonia-stg-lon-svc-01`, `prj-ufonia-fls-trial-lon`,
`prj-ufonia-prd-lon-svc-02`) — the user confirmed Platform COGS is meant to
track the two production projects above instead. The old 8-project scope is
preserved as `bigquery-sql/gcp_uk_r&d_platform_cogs.sql` — see below.

### `bigquery-sql/gcp_us_platform_cogs.sql`

Same shape and same 24 service IDs as `gcp_uk_platform_cogs.sql`, scoped to the
US production project:

- Project: `prj-ufonia-prd-iowa-svc-02` (736494139432, "Dora Advanced Production").

Added 2026-10-05 from a Billing console export, cleaned up the same way as
the other COGS queries (see below). The console version also listed the 5
IDs removed from `gcp_uk_platform_cogs.sql` in August (`9B82-7513-9D1C`,
`C5E6-A27F-6A44`, `FBF2-FC68-171A`, `2062-016F-44A2`, `1DB1-3CD3-35A3`); none
had usage on this project, so they were dropped to keep the two lists the
same. Disjoint project scope from `gcp_uk_platform_cogs.sql`, so never additive
with it. For September 2026, 18 of the 24 IDs matched at least one row.
Sorted `Subtotal DESC` and capped at `LIMIT 10`.

### `` bigquery-sql/gcp_uk_r&d_platform_cogs.sql ``

Renamed from `` gcp_r&d_platform_cogs.sql `` on 2026-10-05; shown as "UK R&D ..." in
the billing dashboard.

Same shape and same 24 service IDs as `gcp_uk_platform_cogs.sql`, scoped to 2
dev projects:

- Projects: `prj-ufonia-dev-host-01` (616882422931), `prj-ufonia-dev-lon-svc-01` (728785948359).

Disjoint project scope from `gcp_uk_platform_cogs.sql` (2 production projects),
not a subset/superset of it, so its total is never additive with the
Platform COGS row. "R&D" is an informal label for this project pair, not an
official GCP/console term. Checked all 24 service IDs against this scope for
August 2026: all 24 matched at least one row — re-check this each run rather
than assuming it stays true. Sorted `Subtotal DESC` and capped at `LIMIT 10`.

**Narrowed 2026-09-01:** originally created as an unmodified copy of
`gcp_uk_platform_cogs.sql` from just before that file's own project-scope
correction, so it briefly covered all 8 of the old dev/staging/trial
projects (`prj-ufonia-dev-iowa-svc-02`, `prj-ufonia-dev-host-01`,
`prj-ufonia-dev-iowa-host-01`, `prj-ufonia-dev-lon-svc-01`,
`prj-ufonia-stg-host-01`, `prj-ufonia-stg-lon-svc-01`,
`prj-ufonia-fls-trial-lon`, `prj-ufonia-prd-lon-svc-02`). The user then
narrowed it, same day, to just the 2 dev projects above.

### `bigquery-sql/gcp_uk_api_cogs.sql`

Renamed from `gcp_api_cogs.sql` on 2026-10-05, to distinguish it from
`gcp_us_platform_cogs.sql`; shown as "UK ..." in the billing dashboard.

Same shape as `gcp_all_services.sql`, scoped to specific projects and services (COGS
for API-based services):

- Projects: `prj-ufonia-prd-lon-svc-01` (870453169286), `prj-ufonia-prd-lon-host-01` (1025855247143)
- Services: `63DE-82AB-F564` (Cloud Speech API)

### `` bigquery-sql/gcp_uk_r&d_api_cogs.sql ``

Renamed from `` gcp_r&d_api_cogs.sql `` on 2026-10-05; shown as "UK R&D ..." in
the billing dashboard.

Same shape and same single service ID (`63DE-82AB-F564`, Cloud Speech API) as
`gcp_uk_api_cogs.sql`, but scoped to the same 2 dev projects as
`` gcp_uk_r&d_platform_cogs.sql `` instead of the 2 production projects:

- Projects: `prj-ufonia-dev-host-01` (616882422931), `prj-ufonia-dev-lon-svc-01` (728785948359)

A copy of `gcp_uk_api_cogs.sql` with only the project filter changed, added
2026-09-01. For August 2026 this returns a single row, Cloud Speech API at
**$0.0072** — de minimis dev usage, not zero, so it still renders (a stat
tile, not "no matching rows"). Disjoint project scope from `gcp_uk_api_cogs.sql`
(2 production projects), so never additive with it — same relationship as
`` gcp_uk_r&d_platform_cogs.sql `` has with `gcp_uk_platform_cogs.sql`.

### `bigquery-sql/aws_services.sql`

Cost by service for the current calendar month (Europe/London; the GCP
queries use US/Pacific to match the Billing console), for AWS account `453829601976`. Sourced from
`bg_dataset_aws_cost_and_usage.aws_cost_and_usage`, a BigQuery table
populated daily by a separate CUR-to-BigQuery import pipeline — see
`aws-bigquery-loader/README.md` for the full design (AWS Data Export → keyless OIDC
federation → Cloud Run Job → BigQuery). Excludes `line_item_type = 'Tax'`,
to match the GCP queries' exclusion of tax rows. Sorted by `Cost DESC` and
capped at `LIMIT 10`, same shape as `gcp_all_services.sql`.

For the previous calendar month instead of the current one, see
`bigquery-sql/aws_monthly_cost.sql` — same `CURRENT_DATE`-relative pattern,
shifted back one month, so it always reflects "last month" without editing.

Note the underlying table's earliest date depends on what's been backfilled
so far (check `MIN(usage_date)` if in doubt) — querying a month before that
returns zero rows.

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

### `bigquery-sql/aws_marketplace.sql`

AWS Marketplace charges for the current calendar month: third-party
products billed through AWS, such as the "(Amazon Bedrock Edition)" Claude
and OpenAI models. They're identified by `line_item_product_code` being a
Marketplace product ID (20+ lowercase letters/digits) rather than an AWS
service code like `AmazonEC2`. Since 2026-10-05, `aws_services.sql`,
`aws_services_by_environment.sql` and both `aws_monthly_cost*.sql` files
exclude these rows. September 2026: $430.95 Marketplace, $5,358.53 AWS
excluding Marketplace ($5,789.48 in all, including VAT).

**VAT (since 2026-10-05):** all the AWS queries include `line_item_type =
'Tax'` rows, so AWS figures include 20% UK VAT and match the AWS console
(September 2026 Production: $1,369.53 + $273.95 VAT = $1,643.48).
Marketplace products carry no VAT. The GCP export has no tax lines.

### `bigquery-sql/aws_services_by_environment.sql`

Same source table and window as `aws_services.sql` (current calendar month),
but split by environment instead of by service: `Production`, `Development`,
or `Uncategorized`. Uses the CUR's `cost_category_production` /
`cost_category_development` columns — an AWS Cost Category configured on
this account — rather than `line_item_usage_account_id`: the payer account
(`453829601976`) has 15 linked member accounts, none individually named
"production" or "development", so the Cost Category is the only clean
prod/dev split available. As of 2026-08, every line item matches one of the
two categories (no `Uncategorized` rows), but the query doesn't assume that
stays true.

For the previous calendar month instead, see
`bigquery-sql/aws_monthly_cost_by_environment.sql` — same
`CURRENT_DATE`-relative shift-back-one-month pattern as
`aws_monthly_cost.sql`.

### `bigquery-sql/vonage_services.sql`

Cost by category (`SMS`, `Inbound Calls`, `Outbound Calls`, `WebSocket`,
`Other`) for the current calendar month (Europe/London; the GCP queries
use US/Pacific to match the Billing console), sourced from
`bq_dataset_vonage_cost_and_usage.vonage_cost_and_usage`, a BigQuery table
populated daily by the Vonage Reports API import pipeline — see
`vonage-bigquery-loader/README.md` for the full design. No `LIMIT` (at most
5 category rows).

**Currency is EUR, not USD** — never combine this query's totals with the
GCP/AWS rows. Every SMS row's `currency` field comes back blank from
Vonage's own API on this account (a data quirk, not a pipeline bug) — the
query sums `total_price` regardless of that, so treat the result as EUR to
match every other category rather than a fully confirmed figure.

This replaced the earlier manual process of dropping Vonage/Nexmo invoice
CSVs into `vonage-bigquery-loader/` by hand — that folder now holds the
pipeline's Terraform/Cloud Run Job code instead of invoice files.

## Changes from the original console-generated queries

All three queries were originally exported as-is from the GCP Billing
Console's query builder, which leaves several placeholders and a hardcoded
date range. Cleanup applied to all three:

- **Parameterized the date range.** Replaced the hardcoded `usage_start_time`
  bounds (e.g. `'2026-08-01T00:00:00 US/Pacific'`) with a rolling
  current-calendar-month window based on `CURRENT_DATE('US/Pacific')`, so
  the query always reflects the current month without manual edits. All
  three queries currently use the current month. `gcp_uk_api_cogs.sql` and
  `gcp_uk_platform_cogs.sql` are intended to run a month in arrears (previous
  calendar month) once a full prior month's data exists in the export
  table — right now the table only contains data from 2026-08-01 onward, so
  a previous-month window returns nothing. To switch them to previous-month,
  change the bounds to:
  `usage_start_time >= TIMESTAMP(DATE_TRUNC(DATE_SUB(CURRENT_DATE('US/Pacific'), INTERVAL 1 MONTH), MONTH), 'US/Pacific')`
  and
  `usage_start_time < TIMESTAMP(DATE_TRUNC(CURRENT_DATE('US/Pacific'), MONTH), 'US/Pacific')`.
- **Timezone: US/Pacific (reverted 2026-10-05).** The queries were briefly
  switched to `Europe/London`, but that shifts the month boundaries 8 hours
  earlier than the GCP Billing console and Google's invoice month, which use
  US/Pacific. For September 2026 that made `gcp_uk_platform_cogs.sql`'s Cost
  $12,990.70 instead of the console's $13,001.11. All six GCP queries now use
  US/Pacific again, so they reconcile with the console. The AWS and Vonage
  queries still use Europe/London calendar dates.
- **Removed the vestigial `spend_cud_fee_skus` CTE.** It was an empty SKU
  list (`UNNEST([''])`) left over from the console template, meaning
  `spend_cud_fee_cost` always evaluated to `0` via an `IN` subquery that could
  never match. Replaced with a literal `0 AS spend_cud_fee_cost`. If CUD
  (Committed Use Discount) commitment fee SKUs need to be excluded in future,
  this is where to reintroduce them.
- **Removed the trailing `- 0`** in the `Subtotal` calculation (harmless but
  vestigial console boilerplate).

Additional fixes specific to `gcp_uk_api_cogs.sql` and `gcp_uk_platform_cogs.sql`:

- **Filled in the credit-type lists.** `cud_credits` and `other_savings` were
  computed from `c.type IN ('')` (an empty placeholder, always `0`). Replaced
  with the same real credit-type lists used in `gcp_all_services.sql` (e.g.
  `COMMITTED_USAGE_DISCOUNT`, `PROMOTION`, `FREE_TIER`, etc.), so these
  columns now actually compute instead of always returning zero.
- **Fixed the `service.id` filter format.** The filters were written as
  `service.id IN ('services/63DE-82AB-F564', ...)`, but the export table
  stores `service.id` as a bare code (e.g. `63DE-82AB-F564`), not prefixed
  with `services/`. The prefix meant the filter never matched anything and
  the query silently returned zero (`gcp_uk_api_cogs.sql`) or far fewer
  (`gcp_uk_platform_cogs.sql`) rows than it should. Removed the `services/` prefix
  from every ID in both queries.

## Known issues

- **`gcp_uk_platform_cogs.sql`'s project scope changed 2026-09-01** (see above).
  Re-checked all 24 current service IDs against the new 2-project production
  scope for August 2026: 23 of 24 matched at least one row. The one
  exception, `82AF-DE7A-51D0` (`Container Registry Vulnerability Scanning`),
  is a real service elsewhere in the export but had zero usage against these
  two production projects last month — left in the filter since it's a valid
  ID that could plausibly see usage in a future month, unlike the
  never-matches-anywhere IDs noted below.
- **`gcp_uk_platform_cogs.sql` previously had 5 `service.id` filter values that
  never matched a row in this query's (then-current) project/date scope** —
  `9B82-7513-9D1C`, `C5E6-A27F-6A44`, `FBF2-FC68-171A`, `1DB1-3CD3-35A3`
  (removed 2026-08-14, none of the four match any service anywhere in the
  export), and `2062-016F-44A2` (removed 2026-08-28 — this one *is* a real,
  valid service ID (`Support`) elsewhere in the export, it just had never had
  any usage against the 8 projects in that older scope). Since all five
  matched zero rows in the query's own output at the time, removing them from
  the filter had no effect on totals; they were dropped to keep the query
  honest about what it was actually scoping.
- **`gcp_uk_api_cogs.sql` previously had `02DA-B362-D983` in its filter, removed
  2026-08-28** — does not match any service anywhere in this billing export
  (checked against the full distinct `service.id` list, with and without the
  `services/` prefix — no match). Either this service has never had usage on
  this billing account, or it was the wrong ID for whatever second API
  `gcp_uk_api_cogs.sql` was meant to cover. Needs the correct service ID adding
  back before this query's totals can be considered complete for "API COGS"
  more broadly than just Cloud Speech API.
