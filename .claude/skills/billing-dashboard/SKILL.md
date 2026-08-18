---
name: billing-dashboard
description: >-
  Runs all three GCP billing queries (services.sql, apicogs.sql,
  platformcogs.sql) plus the AWS query (aws_services.sql), and includes any
  Vonage invoice CSVs dropped in vonage-bigquery-ingress/, publishing a single combined
  dashboard artifact. Use when the user asks to run the billing queries,
  refresh the cost dashboard, or see
  services/apicogs/platformcogs/AWS/Vonage costs "together" or "in one
  place".
---

# Billing dashboard

Runs `bigquery-sql/services.sql`, `bigquery-sql/apicogs.sql`,
`bigquery-sql/platformcogs.sql`, and `bigquery-sql/aws_services.sql` from this repo,
plus any invoice CSVs found in `vonage-bigquery-ingress/`, and renders all of it as one
combined Artifact, instead of separate ones.

## Steps

1. **Run all four queries** against `prj-ufonia-cmn-lon-billing-01`, one
   `bq query --use_legacy_sql=false --project_id=prj-ufonia-cmn-lon-billing-01`
   call per file:
   - `bigquery-sql/services.sql`
   - `bigquery-sql/apicogs.sql`
   - `bigquery-sql/platformcogs.sql`
   - `bigquery-sql/aws_services.sql`

   These can run in parallel (independent Bash calls in one message).
   `services.sql`, `platformcogs.sql`, and `aws_services.sql` are all capped
   at `LIMIT 10`, so for the summary table (step 3a) also run each one's
   un-limited equivalent (same CTE/filters, drop the `LIMIT 10` and the
   `GROUP BY`, just `SUM(...)` everything into one row) to get the true
   month-to-date total for each — the limited results understate the total
   once there are more than 10 services in scope.

1a. **`aws_services.sql` reads from `bg_dataset_aws_cost_and_usage.aws_cost_and_usage`**,
   populated daily by a separate Cloud Run Job (see `aws-bigquery-loader/README.md` for the
   full CUR-to-BigQuery pipeline) — no AWS SSO session needed to query it,
   it's plain BigQuery like the other three. This is a wholly separate cloud
   account/provider from the three GCP queries — never combine its numbers
   into the GCP summary math, even though it happens to also be USD.

1b. **Check for invoice CSVs in `vonage-bigquery-ingress/`.** If any exist, categorize each
   invoice's line items by `SKU` per the scheme in the README (SMS /
   Inbound Calls / Outbound Calls / WebSocket / Other) and sum `Usage` per
   category. Each invoice is its own EUR figure for whatever period it
   covers (not month-to-date, not USD) — give it its own dashboard section
   AND add it as its own row in the summary table (step 3a; user confirmed
   2026-08-17 they want it there for visibility) — but never combine its
   EUR total with any of the USD rows, and never let it imply the table
   sums to a grand total.

2. **Load the `dataviz` skill** before building any chart — it governs form,
   color, marks, and the six-check validation used here.

3. **Pick the form per section, independently**, based on how many rows each
   query actually returned this run (don't assume from a previous run).
   `services.sql`, `platformcogs.sql`, and `aws_services.sql` are all capped
   at `LIMIT 10` (top 10 by Subtotal/Cost) — `apicogs.sql` is not:
   - 1 row → a stat tile (label + value + the savings breakdown), not a
     one-bar chart.
   - 2+ rows → a horizontal bar chart, one hue (`--bar`/sequential blue from
     `references/palette.md`), sorted descending by Subtotal, with a hover
     tooltip carrying the full Cost / Negotiated savings / Savings
     programmes / Other savings / Subtotal breakdown, plus a collapsible
     full data table below the chart. Direct-label every bar's value (not
     just the top few) — these charts are already a curated top-10 list, so
     labeling the full set doesn't clutter it and the user has asked for
     all 10 to show, not just the top 5.
   - 0 rows → say so plainly in that section ("no matching rows this
     period") rather than rendering an empty chart.

3a. **Summary table, at the top of the page, above the sections.** One row
   per query/source — All services (services.sql), API COGS (apicogs.sql),
   Platform COGS (platformcogs.sql), AWS all services (aws_services.sql),
   and one row per Vonage invoice found — with the same Cost / Negotiated
   savings / Savings programmes / Other savings / Subtotal columns, using
   the un-limited totals from step 1, not the top-10 figures. For the AWS
   row, Cost and Subtotal are both the same `UnblendedCost` sum and the
   three savings columns are `0` (no breakdown available yet — see step
   1a). For each Vonage row, Cost and Subtotal are both the invoice's
   total (all SKU categories summed) in **EUR**, three savings columns
   `0` — make the table currency-aware per row (don't render the EUR
   figure with a `$` prefix). No grand-total row and no summed "total of
   totals": API COGS and Platform COGS are cost subsets of the same overall
   spend in the first row (specific projects/services), not spend on top of
   it, so adding them together would double-count; AWS is a wholly separate
   cloud account, not a subset of or addition to the GCP rows either;
   Vonage is a different currency entirely on top of that. Say all of this
   explicitly in a caption under the table — user confirmed (2026-08-14)
   they want AWS as a row in this table, and (2026-08-17) Vonage too, not
   separate cards only — so keep both there on future runs.

4. **Build one HTML page with a stacked section per source**, in this
   order: services, platformcogs, apicogs, AWS costs, then one section per
   Vonage invoice found (if any). Reuse the shared visual language from
   prior dashboards in this project: card-on-page layout, the light/dark
   CSS custom-property block from `references/palette.md`, same
   fonts/spacing. Each section gets its own eyebrow + heading identifying
   which query/file it came from and the date range it covers (services.sql
   = current month; apicogs/platformcogs = current month for now, see
   README's note about switching to previous-month once a full prior
   month's data exists; aws_services.sql = current calendar month,
   Europe/London, same as services.sql; each Vonage invoice = whatever
   single date/period it covers). Label the AWS section clearly with its
   account (`453829601976`) and currency (USD, same as the GCP figures, but
   a wholly separate spend — don't let the shared currency symbol imply
   they're combinable). Label each Vonage
   section with its invoice number and currency (EUR) — a different
   currency from GCP/AWS, so use a currency-aware formatter (see the
   `fmt`/`fmtCompact`/`renderSimpleBarChart`/`renderSimpleTable` currency
   parameter already in the dashboard's script) rather than hardcoding `$`.

5. **Surface known data-quality caveats inline**, next to the section they
   apply to, rather than assuming they're still true — re-derive them from
   the actual query output each run:
   - `apicogs.sql`: flag any `service.id` filter value that appears in the
     query's WHERE clause but not in the returned rows (e.g. the unresolved
     `02DA-B362-D983` — check README's Known issues for current status).
   - `platformcogs.sql`: same check, currently 4 unresolved IDs (see
     README).
   - AWS section: note that this only shows `UnblendedCost` (no
     negotiated-savings/RI/SP-discount breakdown yet, unlike the GCP
     sections) — see README's parity note. Also note the data only goes
     back to when the CUR export started (2026-08-01 as of this writing —
     check `aws-bigquery-loader/README.md` for the current earliest date) — a
     previous-month AWS section will return zero rows until then.
   - Vonage section(s): note the currency (EUR) and that the figure is a
     single invoice/period, not month-to-date — don't let it get compared
     directly against the GCP/AWS numbers without that caveat.

6. **Publish as a single Artifact.** Before publishing, call
   `Artifact({action: "list"})` and reuse the URL of an existing "Billing
   Dashboard" artifact if one exists (pass it as `url`), so repeat runs
   update the same link instead of creating a new one each time. Title:
   "Billing Dashboard". Favicon: 📊.

Write the working HTML file to the session scratchpad directory, not into
this repo.
