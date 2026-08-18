---
name: billing-dashboard
description: >-
  Runs all three GCP billing queries (gcp_all_services.sql, gcp_api_cogs.sql,
  gcp_platform_cogs.sql) plus the AWS query (aws_services.sql) and the Vonage
  query (vonage_services.sql), publishing a single combined dashboard
  artifact. Use when the user asks to run the billing queries, refresh the
  cost dashboard, or see
  services/apicogs/platformcogs/AWS/Vonage costs "together" or "in one
  place".
---

# Billing dashboard

Runs `bigquery-sql/gcp_all_services.sql`, `bigquery-sql/gcp_api_cogs.sql`,
`bigquery-sql/gcp_platform_cogs.sql`, `bigquery-sql/aws_services.sql`, and
`bigquery-sql/vonage_services.sql` from this repo, and renders all of it as
one combined Artifact, instead of separate ones.

## Steps

1. **Run all five queries** against `prj-ufonia-cmn-lon-billing-01`, one
   `bq query --use_legacy_sql=false --project_id=prj-ufonia-cmn-lon-billing-01`
   call per file:
   - `bigquery-sql/gcp_all_services.sql`
   - `bigquery-sql/gcp_api_cogs.sql`
   - `bigquery-sql/gcp_platform_cogs.sql`
   - `bigquery-sql/aws_services.sql`
   - `bigquery-sql/vonage_services.sql`

   These can run in parallel (independent Bash calls in one message).
   `gcp_all_services.sql`, `gcp_platform_cogs.sql`, and `aws_services.sql` are all capped
   at `LIMIT 10`, so for the summary table (step 3a) also run each one's
   un-limited equivalent (same CTE/filters, drop the `LIMIT 10` and the
   `GROUP BY`, just `SUM(...)` everything into one row) to get the true
   month-to-date total for each — the limited results understate the total
   once there are more than 10 services in scope. `gcp_api_cogs.sql` and
   `vonage_services.sql` have no `LIMIT` (at most 2 and 5 rows respectively),
   so their own output already is the true total — just sum their rows for
   the summary row, no separate unlimited query needed for either.

1a. **`aws_services.sql` reads from `bg_dataset_aws_cost_and_usage.aws_cost_and_usage`**,
   populated daily by a separate Cloud Run Job (see `aws-bigquery-loader/README.md` for the
   full CUR-to-BigQuery pipeline) — no AWS SSO session needed to query it,
   it's plain BigQuery like the other four. This is a wholly separate cloud
   account/provider from the three GCP queries — never combine its numbers
   into the GCP summary math, even though it happens to also be USD.

1b. **`vonage_services.sql` reads from `bq_dataset_vonage_cost_and_usage.vonage_cost_and_usage`**,
   populated daily by its own Cloud Run Job (see `vonage-bigquery-loader/README.md`) —
   no manual invoice CSV drop needed any more, this replaced that entirely.
   Returns cost by category (SMS / Inbound Calls / Outbound Calls /
   WebSocket / Other) for the current calendar month. **Currency is EUR,
   not USD** — never combine its numbers into the GCP/AWS summary math.
   Every SMS row's `currency` field comes back blank from Vonage's own API
   on this account (a data quirk, not a pipeline bug) — the query sums
   `total_price` regardless, so treat the figure as EUR to match every
   other category rather than a fully confirmed one.

2. **Load the `dataviz` skill** before building any chart — it governs form,
   color, marks, and the six-check validation used here.

3. **Pick the form per section, independently**, based on how many rows each
   query actually returned this run (don't assume from a previous run).
   `gcp_all_services.sql`, `gcp_platform_cogs.sql`, and `aws_services.sql` are all capped
   at `LIMIT 10` (top 10 by Subtotal/Cost) — `gcp_api_cogs.sql` and
   `vonage_services.sql` are not:
   - 1 row → a stat tile (label + value + the savings breakdown if
     available), not a one-bar chart.
   - 2+ rows → a horizontal bar chart, one hue (`--bar`/sequential blue from
     `references/palette.md`), sorted descending by Subtotal/Cost, with a hover
     tooltip carrying the full breakdown where one exists (Cost / Negotiated
     savings / Savings programmes / Other savings / Subtotal for the GCP
     queries; just Cost for AWS/Vonage, which don't have a savings
     breakdown), plus a collapsible full data table below the chart.
     Direct-label every bar's value (not just the top few) — these charts
     are already a curated/small list, so labeling the full set doesn't
     clutter it.
   - 0 rows → say so plainly in that section ("no matching rows this
     period") rather than rendering an empty chart.

3a. **Summary table, at the top of the page, above the sections.** One row
   per query/source — All services (gcp_all_services.sql), API COGS
   (gcp_api_cogs.sql), Platform COGS (gcp_platform_cogs.sql), AWS all
   services (aws_services.sql), Vonage all categories (vonage_services.sql)
   — with the same Cost / Negotiated savings / Savings programmes / Other
   savings / Subtotal columns, using the un-limited totals from step 1, not
   the top-10 figures. For the AWS row, Cost and Subtotal are both the same
   `UnblendedCost` sum and the three savings columns are `0` (no breakdown
   available yet — see step 1a). For the Vonage row, Cost and Subtotal are
   both the sum of `vonage_services.sql`'s rows, in **EUR**, three savings
   columns `0` (no savings/discount breakdown for Vonage either) — make the
   table currency-aware per row (don't render the EUR figure with a `$`
   prefix). No grand-total row and no summed "total of totals": API COGS
   and Platform COGS are cost subsets of the same overall spend in the
   first row (specific projects/services), not spend on top of it, so
   adding them together would double-count; AWS is a wholly separate cloud
   account, not a subset of or addition to the GCP rows either; Vonage is a
   different currency entirely on top of that. Say all of this explicitly
   in a caption under the table — user confirmed (2026-08-14) they want AWS
   as a row in this table, and (2026-08-17) Vonage too — so keep both there
   on future runs.

4. **Build one HTML page with a stacked section per source**, in this
   order: services, platformcogs, apicogs, AWS costs, Vonage costs. Reuse
   the shared visual language from prior dashboards in this project:
   card-on-page layout, the light/dark CSS custom-property block from
   `references/palette.md`, same fonts/spacing. Each section gets its own
   eyebrow + heading identifying which query/file it came from and the
   date range it covers (gcp_all_services.sql = current month;
   gcp_api_cogs/gcp_platform_cogs = current month for now, see README's
   note about switching to previous-month once a full prior month's data
   exists; aws_services.sql and vonage_services.sql = current calendar
   month, Europe/London, same window as gcp_all_services.sql). Label the
   AWS section clearly with its account (`453829601976`) and currency
   (USD, same as the GCP figures, but a wholly separate spend — don't let
   the shared currency symbol imply they're combinable). Label the Vonage
   section clearly with its currency (EUR) — a different currency from
   GCP/AWS, so use a currency-aware formatter (see the
   `fmt`/`fmtCompact`/`renderSimpleBarChart`/`renderSimpleTable` currency
   parameter already in the dashboard's script) rather than hardcoding `$`.

5. **Surface known data-quality caveats inline**, next to the section they
   apply to, rather than assuming they're still true — re-derive them from
   the actual query output each run:
   - `gcp_api_cogs.sql`: flag any `service.id` filter value that appears in the
     query's WHERE clause but not in the returned rows (e.g. the unresolved
     `02DA-B362-D983` — check README's Known issues for current status).
   - `gcp_platform_cogs.sql`: same check, currently 4 unresolved IDs (see
     README).
   - AWS section: note that this only shows `UnblendedCost` (no
     negotiated-savings/RI/SP-discount breakdown yet, unlike the GCP
     sections) — see README's parity note. Also note the data only goes
     back to when the CUR export started (check `aws-bigquery-loader/README.md`
     for the current earliest date) — a previous-month AWS section will
     return zero rows before then.
   - Vonage section: note the currency (EUR) and the blank-`currency`-field
     quirk on SMS rows (see step 1b) — don't let the figure get compared
     directly against the GCP/AWS numbers without that caveat. If a
     category (typically "Other"/VOICE-TTS) returns $0 or is missing
     entirely, that's expected — say so rather than treating it as an
     error.

6. **Publish as a single Artifact.** Before publishing, call
   `Artifact({action: "list"})` and reuse the URL of an existing "Billing
   Dashboard" artifact if one exists (pass it as `url`), so repeat runs
   update the same link instead of creating a new one each time. Title:
   "Billing Dashboard". Favicon: 📊.

Write the working HTML file to the session scratchpad directory, not into
this repo.
