---
name: billing-dashboard
description: >-
  Runs all three GCP billing queries (services.sql, apicogs.sql,
  platformcogs.sql) plus the AWS Cost Explorer query (aws/services.sh)
  against the billing export table and publishes a single combined dashboard
  artifact. Use when the user asks to run the billing queries, refresh the
  cost dashboard, or see services/apicogs/platformcogs/AWS costs "together"
  or "in one place".
---

# Billing dashboard

Runs `bigquery/services.sql`, `bigquery/apicogs.sql`,
`bigquery/platformcogs.sql`, and `aws/services.sh` from this repo and
renders all four results as one combined Artifact, instead of separate ones.

## Steps

1. **Run all three queries** against `prj-ufonia-cmn-lon-billing-01`, one
   `bq query --use_legacy_sql=false --project_id=prj-ufonia-cmn-lon-billing-01`
   call per file:
   - `bigquery/services.sql`
   - `bigquery/apicogs.sql`
   - `bigquery/platformcogs.sql`

   These can run in parallel (independent Bash calls in one message).
   `services.sql` and `platformcogs.sql` are both capped at `LIMIT 10`, so
   for the summary table (step 3a) also run each one's un-limited
   equivalent (same CTE/filters, drop the `LIMIT 10` and the
   `GROUP BY service.description`, just `SUM(...)` everything into one row)
   to get the true month-to-date total for each — the limited results
   understate the total once there are more than 10 services in scope.

1a. **Also run `aws/services.sh`** (requires an active AWS SSO session for
   `AdministratorAccess-102369858221` — if it errors with an expired/invalid
   token, tell the user to run
   `aws sso login --profile AdministratorAccess-102369858221` themselves and
   retry, don't try to log in on their behalf). Shape the raw JSON with `jq`
   per the pipelines in the README: top 10 services by `UnblendedCost`
   descending for the chart, and the unlimited sum across all services for
   the summary. This is a wholly separate cloud account/provider from the
   three GCP queries — never combine its numbers into the GCP summary math,
   even though it happens to also be USD.

2. **Load the `dataviz` skill** before building any chart — it governs form,
   color, marks, and the six-check validation used here.

3. **Pick the form per section, independently**, based on how many rows each
   query actually returned this run (don't assume from a previous run).
   `services.sql` and `platformcogs.sql` are both capped at `LIMIT 10` (top
   10 by Subtotal) — `apicogs.sql` is not:
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
   per query — All services (services.sql), API COGS (apicogs.sql),
   Platform COGS (platformcogs.sql), AWS all services (aws/services.sh) —
   with the same Cost / Negotiated savings / Savings programmes / Other
   savings / Subtotal columns, using the un-limited totals from step 1, not
   the top-10 figures. For the AWS row, Cost and Subtotal are both the same
   `UnblendedCost` sum and the three savings columns are `0` (no breakdown
   available yet — see step 1a). No grand-total row and no summed "total of
   totals": API COGS and Platform COGS are cost subsets of the same overall
   spend in the first row (specific projects/services), not spend on top of
   it, so adding them together would double-count; AWS is a wholly separate
   cloud account, not a subset of or addition to the GCP rows either. Say
   both of these explicitly in a caption under the table — user confirmed
   (2026-08-14) they want AWS as a row in this table, not a separate
   card/section, so keep it there on future runs.

4. **Build one HTML page with four stacked sections**, in this order:
   services, platformcogs, apicogs, AWS costs. Reuse the shared visual
   language from prior dashboards in this project: card-on-page layout, the
   light/dark CSS custom-property block from `references/palette.md`, same
   fonts/spacing. Each section gets its own eyebrow + heading identifying
   which query it came from and the date range it covers (services.sql =
   current month; apicogs/platformcogs = current month for now, see
   README's note about switching to previous-month once a full prior
   month's data exists; aws/services.sh = current calendar month to date,
   UTC). Label the AWS section clearly with its account
   (`102369858221`) and currency (USD, same as the GCP figures, but a
   wholly separate spend — don't let the shared currency symbol imply
   they're combinable).

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
     sections) — see README's parity note.

6. **Publish as a single Artifact.** Before publishing, call
   `Artifact({action: "list"})` and reuse the URL of an existing "Billing
   Dashboard" artifact if one exists (pass it as `url`), so repeat runs
   update the same link instead of creating a new one each time. Title:
   "Billing Dashboard". Favicon: 📊.

Write the working HTML file to the session scratchpad directory, not into
this repo.
