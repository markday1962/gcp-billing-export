---
name: billing-dashboard
description: >-
  Runs all eight billing queries — five GCP (gcp_all_services.sql,
  gcp_api_cogs.sql, gcp_platform_cogs.sql, gcp_r&d_platform_cogs.sql,
  gcp_r&d_api_cogs.sql), two AWS (aws_services.sql,
  aws_services_by_environment.sql), and Vonage (vonage_services.sql) —
  publishing a single combined dashboard artifact. All eight totals appear in
  the summary table (GCP's four sub-sources and AWS's Production/Development
  split as indented rows); Vonage is the only source that still gets its own
  detail chart below it. Use when the user asks to run the billing queries, refresh the
  cost dashboard, or see
  gcp_all_services/gcp_api_cogs/gcp_platform_cogs/gcp_r&d_platform_cogs/gcp_r&d_api_cogs/AWS/Vonage
  costs "together" or "in one place".
---

# Billing dashboard

Runs `bigquery-sql/gcp_all_services.sql`, `bigquery-sql/gcp_api_cogs.sql`,
`bigquery-sql/gcp_platform_cogs.sql`, `` bigquery-sql/gcp_r&d_platform_cogs.sql ``,
`` bigquery-sql/gcp_r&d_api_cogs.sql ``,
`bigquery-sql/aws_services.sql` (or `aws_monthly_cost.sql` for last month),
`bigquery-sql/aws_services_by_environment.sql` (or
`aws_monthly_cost_by_environment.sql` for last month), and
`bigquery-sql/vonage_services.sql` from this repo, and renders all of it as
one combined Artifact, instead of separate ones.

**Layout, as of 2026-09-01 (see step 3a/4 history):** the summary table at
the top carries all eight totals — this is the primary output. Below it,
only **one** source gets its own detail chart card: Vonage. The other seven
(All services, Platform COGS, R&D Platform COGS, API COGS, R&D API COGS, AWS
top-10-by-service, AWS by-environment) were trimmed from detail-panel form —
run their queries anyway, since the summary table still needs their totals,
but don't build a chart/table section for them. AWS's Production/Development
split moved from its own chart into two indented sub-rows under "AWS All
services" in the summary table itself (see step 3a); GCP's Platform
COGS/R&D Platform COGS/API COGS/R&D API COGS became indented (grouping-only,
non-additive) sub-rows under "GCP All services" the same way — none of them
disappeared, they just moved into the table.

## Steps

1. **Run all eight queries** against `prj-ufonia-cmn-lon-billing-01`, one
   `bq query --use_legacy_sql=false --project_id=prj-ufonia-cmn-lon-billing-01`
   call per file:
   - `bigquery-sql/gcp_all_services.sql`
   - `bigquery-sql/gcp_api_cogs.sql`
   - `bigquery-sql/gcp_platform_cogs.sql`
   - `` bigquery-sql/gcp_r&d_platform_cogs.sql ``
   - `` bigquery-sql/gcp_r&d_api_cogs.sql ``
   - `bigquery-sql/aws_services.sql`
   - `bigquery-sql/aws_services_by_environment.sql`
   - `bigquery-sql/vonage_services.sql`

   These can run in parallel (independent Bash calls in one message — quote
   filenames containing `&`, e.g. `"bigquery-sql/gcp_r&d_platform_cogs.sql"`
   and `"bigquery-sql/gcp_r&d_api_cogs.sql"`, since `&` is a shell
   metacharacter). All eight are needed even though only two get their own
   chart — the summary table (step 3a) uses every one of them.

   `gcp_all_services.sql`, `gcp_platform_cogs.sql`, `` gcp_r&d_platform_cogs.sql ``,
   and `aws_services.sql` are all capped
   at `LIMIT 10`, so for the summary table also run each one's
   un-limited equivalent (same CTE/filters, drop the `LIMIT 10` and the
   `GROUP BY`, just `SUM(...)` everything into one row) to get the true
   month-to-date total for each — the limited results understate the total
   once there are more than 10 services in scope. `gcp_api_cogs.sql`,
   `` gcp_r&d_api_cogs.sql ``, `vonage_services.sql`, and
   `aws_services_by_environment.sql` have no
   `LIMIT` (at most 2, 1, 5, and 3 rows respectively), so their own output
   already is the true total — just sum their rows for the summary row (for
   `aws_services_by_environment.sql`, this sum should equal
   `aws_services.sql`'s unlimited total — see step 1a), no separate unlimited
   query needed for any of the four.

1a. **`aws_services.sql` and `aws_services_by_environment.sql` both read from
   `bg_dataset_aws_cost_and_usage.aws_cost_and_usage`**,
   populated daily by a separate Cloud Run Job (see `aws-bigquery-loader/README.md` for the
   full CUR-to-BigQuery pipeline) — no AWS SSO session needed to query it,
   it's plain BigQuery like the other four. This is a wholly separate cloud
   account/provider from the three GCP queries — never combine its numbers
   into the GCP summary math, even though it happens to also be USD.
   `aws_services_by_environment.sql` splits the same total by
   `Production`/`Development`/`Uncategorized` using the CUR's
   `cost_category_production`/`cost_category_development` columns (an AWS
   Cost Category configured on this account) — **not** a split across
   separate AWS accounts. The payer account (`453829601976`) actually has 15
   linked member accounts, none individually named "production" or
   "development"; the Cost Category is the only clean prod/dev split
   available. Its rows should sum to the same total as
   `aws_services.sql`'s unlimited total — if they don't, note the gap rather
   than silently reconciling it. **As of 2026-09-01 this split lives in the
   summary table** (two indented sub-rows under "AWS All services" — see step
   3a), not its own chart card.

1a-2. **`` gcp_r&d_platform_cogs.sql `` is a same-shape sibling of `gcp_platform_cogs.sql`**,
   not a subset/superset relationship the way API COGS and Platform COGS are.
   History: until 2026-09-01, `gcp_platform_cogs.sql` itself scoped to 8
   dev/staging/trial projects; the user then corrected it to scope to the
   two actual production projects (`prj-ufonia-prd-lon-host-01`,
   `prj-ufonia-prd-lon-svc-01` — same two as `gcp_api_cogs.sql`). ``
   gcp_r&d_platform_cogs.sql `` started as an unmodified copy of the file
   from just before that correction (briefly covering all 8 of the old
   dev/staging/trial projects), then was narrowed the same day to just 2 of
   them: `prj-ufonia-dev-host-01` (616882422931),
   `prj-ufonia-dev-lon-svc-01` (728785948359) — same 24 service IDs, same
   shape, just this 2-project scope now. Treat it as
   its own independent source in the summary table (not additive with
   Platform COGS, similarly to how AWS isn't additive with the GCP rows —
   different project scope entirely, just happens to share a query shape).
   No longer gets its own chart card (trimmed 2026-09-01) — summary table row
   only.

1a-3. **`` gcp_r&d_api_cogs.sql `` is the same relationship, one level down**:
   a copy of `gcp_api_cogs.sql` (same single service ID, `63DE-82AB-F564`
   Cloud Speech API) re-scoped to the same 2 dev projects as ``
   gcp_r&d_platform_cogs.sql `` (`prj-ufonia-dev-host-01`,
   `prj-ufonia-dev-lon-svc-01`) instead of `gcp_api_cogs.sql`'s 2 production
   projects. Added 2026-09-01. Typically returns exactly 1 row and a very
   small figure (August 2026: $0.0072) — de minimis dev usage, not zero, so
   render it as a stat tile (per step 3), not "no matching rows". Disjoint
   project scope from `gcp_api_cogs.sql`, never additive with it. **No longer
   gets its own chart card (trimmed 2026-09-01)** — it's now an indented
   `sub-row` under "GCP All services" in the summary table only, same as
   Platform COGS and R&D Platform COGS — see step 3a.

1b. **`vonage_services.sql` reads from `bq_dataset_vonage_cost_and_usage.vonage_cost_and_usage`**,
   populated daily by its own Cloud Run Job (see `vonage-bigquery-loader/README.md`) —
   no manual invoice CSV drop needed any more, this replaced that entirely.
   Returns cost by category (SMS / Inbound Calls / Outbound Calls /
   WebSocket / Other) for the current calendar month. **Currency is EUR,
   not USD** — never combine its numbers into the GCP/AWS summary math.
   Every SMS row's `currency` field comes back blank from Vonage's own API
   on this account (a data quirk, not a pipeline bug) — the query sums
   `total_price` regardless, so treat the figure as EUR to match every
   other category rather than a fully confirmed one. **The only source that
   still gets its own chart card** — see step 4.

2. **Load the `dataviz` skill** before building the one remaining chart
   (Vonage) — it governs form, color, marks, and the six-check
   validation used here.

3. **Pick the chart form for Vonage** — the only source that still gets a
   detail card as of 2026-09-01 — based on
   how many rows `vonage_services.sql` actually returned this run (don't
   assume from a
   previous run):
   - 1 row → a stat tile (label + value + the savings breakdown if
     available), not a one-bar chart.
   - 2+ rows → a horizontal bar chart, one hue (`--bar`/sequential blue from
     `references/palette.md`), sorted descending by Subtotal/Cost, with a hover
     tooltip carrying the full breakdown where one exists, plus a
     collapsible full data table below the chart. Direct-label every bar's
     value (not just the top few) — these charts are already a curated/small
     list, so labeling the full set doesn't clutter it. `vonage_services.sql`
     normally lands here (5 rows).
   - 0 rows → say so plainly in that section ("no matching rows this
     period") rather than rendering an empty chart.

   The other seven sources (All services, Platform COGS, R&D Platform COGS,
   API COGS, R&D API COGS, AWS top-10-by-service, AWS by-environment) don't
   get a chart at
   all as of 2026-09-01 — their totals go into the summary table only (step
   3a). Don't re-add detail cards for them without the user asking.

3a. **Summary table, at the top of the page, above the sections.** Rows, in
   this order — `sub-row` = the CSS class from step 3a's styling note below
   (lighter weight, `↳` prefix, `padding-left: 30px` on the first cell — see
   the published dashboard's `<style>` block for the exact rule):
   - GCP All services (gcp_all_services.sql)
   - `sub-row`: ↳ GCP Platform COGS (gcp_platform_cogs.sql)
   - `sub-row`: ↳ GCP R&D Platform COGS (`` gcp_r&d_platform_cogs.sql ``)
   - `sub-row`: ↳ GCP API COGS (gcp_api_cogs.sql)
   - `sub-row`: ↳ GCP R&D API COGS (`` gcp_r&d_api_cogs.sql ``)
   - AWS All services (aws_services.sql)
   - `sub-row`: ↳ AWS Development (aws_services_by_environment.sql)
   - `sub-row`: ↳ AWS Production (aws_services_by_environment.sql)
   - Vonage all categories (vonage_services.sql)

   Same Cost / Negotiated savings / Savings programmes / Other
   savings / Subtotal columns throughout, using the un-limited totals from
   step 1, not
   the top-10 figures. For the AWS rows, Cost and Subtotal are both the same
   `UnblendedCost` sum and the three savings columns are `0` (no breakdown
   available yet — see step 1a). For the Vonage row, Cost and Subtotal are
   both the sum of `vonage_services.sql`'s rows, in **EUR**, three savings
   columns `0` (no savings/discount breakdown for Vonage either) — make the
   table currency-aware per row (don't render the EUR figure with a `$`
   prefix).

   **The `sub-row` styling means two different things depending which parent
   it's under — get this right, it's a common source of confusion (user
   flagged it 2026-09-01):**
   - Under **AWS All services**, the two sub-rows (Development, Production)
     **do sum exactly** to the parent row — a full, non-overlapping 2-way
     split of 100% of AWS spend (from `aws_services_by_environment.sql`, or
     `aws_monthly_cost_by_environment.sql` for last month). This is the one
     place in the table where indentation means "this decomposes the row
     above."
   - Under **GCP All services**, the four sub-rows (Platform COGS, R&D
     Platform COGS, API COGS, R&D API COGS) **do not sum** to the parent, nor
     to each other, nor combined to All services. They're indented purely to
     group them visually as GCP-scoped detail rows — not as a decomposition.
     Platform COGS and API COGS are genuine cost *subsets* of All services
     (specific projects/services within the same GCP spend — GCP All
     services has no project/service filter, so it's a superset of both),
     but All services also covers the entire rest of the account, so neither
     sums to it, and they don't sum to each other either (Platform COGS's 24
     service IDs deliberately exclude Cloud Speech API, the one API COGS
     covers — two disjoint slices of the same 2 production projects, "platform
     (non-API) COGS" per the README). R&D Platform COGS and R&D API COGS have
     that same disjoint-from-each-other relationship, but on a *different*
     project scope entirely (2 dev projects, not the 2 production projects
     the non-R&D rows use) — so none of the four reconcile against each
     other or against All services.
   - Vonage is a different currency (EUR) on top of all of this — never mix
     it into any of the above sums even hypothetically.
   - **Because the same visual pattern (indentation) carries opposite
     meanings for the two parents, the caption under the table MUST spell out
     the distinction explicitly** — don't rely on a reader inferring it from
     context, and don't drop this caveat even if the table looks
     self-explanatory. No grand-total row is shown, since a literal sum would
     mix currencies and double-count/misrepresent the GCP subsets.

   History: user confirmed (2026-08-14) they want AWS
   as a row in this table, (2026-08-17) Vonage too, (2026-09-01) both R&D
   Platform COGS and R&D API COGS too, (2026-09-01, later the same day) the
   AWS Development/Production sub-rows, and (2026-09-01, later still) the
   GCP grouping described above — so keep all of this on future runs.

4. **Build one HTML page: summary table, then exactly one detail chart
   card** — `vonage` (bar chart). No other source gets a chart card as of
   2026-09-01 (see the
   layout note at the top of this file and step 3's list) — a prior version
   of this dashboard had seven more cards (All services, Platform COGS, R&D
   Platform COGS, API COGS, R&D API COGS, AWS top-10, AWS by-environment);
   the user had
   them removed over three turns on 2026-09-01: first the five GCP/AWS-top10
   ones, then the AWS-by-environment one (its data moved into the summary
   table as sub-rows), then R&D API COGS (also moved into the summary table,
   as a sub-row under GCP All services alongside Platform COGS/R&D Platform
   COGS/API COGS). Reuse
   the shared visual language from prior dashboards in this project:
   card-on-page layout, the light/dark CSS custom-property block from
   `references/palette.md`, same fonts/spacing. The remaining section gets
   its own eyebrow + heading identifying which query/file it came from and
   the date range it covers (`vonage_services.sql` = current calendar
   month, Europe/London). Label the Vonage
   section clearly with its currency (EUR) — a different currency from
   GCP/AWS, so use a currency-aware formatter (see the
   `fmt`/`fmtCompact`/`renderSimpleBarChart`/`renderSimpleTable` currency
   parameter already in the dashboard's script) rather than hardcoding `$`.

5. **Surface known data-quality caveats inline**, next to the section they
   apply to (Vonage is the only remaining chart card), and in the summary
   caption (for everything else) — rather than assuming they're still true,
   re-derive them from the actual query output each run:
   - Vonage section (has a chart card): note the currency (EUR) and the
     blank-`currency`-field
     quirk on SMS rows (see step 1b) — don't let the figure get compared
     directly against the GCP/AWS numbers without that caveat. If a
     category (typically "Other"/VOICE-TTS) returns $0 or is missing
     entirely, that's expected — say so rather than treating it as an
     error.
   - `gcp_api_cogs.sql` (summary row only): flag any `service.id` filter
     value that appears in the
     query's WHERE clause but not in the returned rows (e.g. the unresolved
     `02DA-B362-D983` — check README's Known issues for current status) — put
     this caveat in the summary caption since there's no dedicated card for
     it any more.
   - `gcp_platform_cogs.sql` (summary row only): same check — as of the
     2026-09-01 project-scope
     correction, 23 of 24 service IDs match at least one row against the new
     2-project production scope; `82AF-DE7A-51D0` (Container Registry
     Vulnerability Scanning) is valid but had zero usage there last month
     (see README's Known issues) — re-derive this each run rather than
     assuming it's still true.
   - `` gcp_r&d_platform_cogs.sql `` (summary row only): note explicitly
     that despite the "R&D"
     label being informal (not an official GCP/billing-console term), this
     query's 2-project scope (`prj-ufonia-dev-host-01`,
     `prj-ufonia-dev-lon-svc-01`) descends from what `gcp_platform_cogs.sql`
     itself used to cover (8 dev/staging/trial projects) before the
     2026-09-01 correction, then was narrowed further the same day. All 24
     service IDs matched at least one row against this 2-project scope as of
     August 2026 (see README) — re-derive this each run rather than assuming
     it stays true.
   - `` gcp_r&d_api_cogs.sql `` (summary row only, chart card removed
     2026-09-01): same query/service as
     `gcp_api_cogs.sql`,
     disjoint project scope (2 dev projects — see step 1a-3). Normally 1 row
     with a very small figure (August 2026: $0.0072) — de minimis usage, not
     an error; a near-zero value isn't the same as "0 rows" (don't drop the
     row from the summary table because the figure looks negligible).
   - AWS All services + sub-rows (summary rows only): note that the top-line
     total only reflects `UnblendedCost` (no
     negotiated-savings/RI/SP-discount breakdown yet) — see README's parity
     note. Also note the data only goes
     back to when the CUR export started (check `aws-bigquery-loader/README.md`
     for the current earliest date) — a previous-month figure will
     be zero before then. For the two sub-rows specifically: "Production" and
     "Development" are an AWS Cost Category (a tagging/rules-based
     classification), not separate AWS accounts — the payer account has 15
     linked member accounts, none individually named this way. If a 3rd,
     "Uncategorized" value appears (none did as of 2026-08), surface it as a
     third sub-row rather than dropping it — it just means some line item
     didn't match either Cost Category rule that month.

6. **Publish as a single Artifact.** Before publishing, call
   `Artifact({action: "list"})` and reuse the URL of an existing "Billing
   Dashboard" artifact if one exists (pass it as `url`), so repeat runs
   update the same link instead of creating a new one each time. Title:
   "Billing Dashboard". Favicon: 📊.

Write the working HTML file to the session scratchpad directory, not into
this repo.
