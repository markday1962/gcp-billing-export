---
name: billing-dashboard
description: >-
  Runs all twelve billing queries — nine GCP (gcp_invoice.sql, gcp_all_services.sql, gcp_all_production.sql, gcp_all_development.sql,
  gcp_uk_api_cogs.sql, gcp_uk_platform_cogs.sql, gcp_us_platform_cogs.sql, gcp_uk_r&d_platform_cogs.sql,
  gcp_uk_r&d_api_cogs.sql), two AWS (aws_services.sql,
  aws_services_by_environment.sql), and Vonage (vonage_services.sql) —
  publishing a single combined dashboard artifact. All twelve totals appear in
  the summary table (GCP's COGS rows, AWS's Production/Development split and
  Vonage's categories as indented rows), followed by a detail card with the
  full list for every source — all costs in one dashboard. GCP uses
  US/Pacific month boundaries to match the Billing console. Use when the user asks to run the billing queries, refresh the
  cost dashboard, or see
  gcp_all_services/gcp_uk_api_cogs/gcp_uk_platform_cogs/gcp_uk_r&d_platform_cogs/gcp_uk_r&d_api_cogs/AWS/Vonage
  costs "together" or "in one place".
---

# Billing dashboard

Runs `bigquery-sql/gcp_all_services.sql`, `bigquery-sql/gcp_uk_api_cogs.sql`,
`bigquery-sql/gcp_uk_platform_cogs.sql`, `bigquery-sql/gcp_us_platform_cogs.sql`,
`` bigquery-sql/gcp_uk_r&d_platform_cogs.sql ``,
`` bigquery-sql/gcp_uk_r&d_api_cogs.sql ``,
`bigquery-sql/aws_services.sql` (or `aws_monthly_cost.sql` for last month),
`bigquery-sql/aws_services_by_environment.sql` (or
`aws_monthly_cost_by_environment.sql` for last month), and
`bigquery-sql/vonage_services.sql` from this repo, and renders all of it as
one combined Artifact, instead of separate ones.

**Layout, as of 2026-10-05 — supersedes everything below about trimmed
cards:** the user wants **all costs in one dashboard**. Keep the summary
table at the top (step 3a), then one detail card per source, in this order,
each with a top-10 bar chart (where it has more than one row) and its
**full** list as a static HTML table, open by default, with a total row:
GCP all services (full list from `gcp_all_services.sql` with `LIMIT 10`
removed), GCP UK Platform COGS, GCP US Platform COGS, GCP UK R&D Platform
COGS (each with `LIMIT 10` removed), GCP API COGS (the UK and UK R&D rows
side by side, no combined total), AWS (environment split table, top-10
chart, full service list from `aws_services.sql` with `LIMIT 10` removed),
then Vonage (step 4 / the full Vonage breakdown note). Check every full list
sums to its summary row. In the chat reply, always report every source —
GCP, AWS and Vonage — never just the one that changed. Where the older text
below says "only Vonage gets a card" or "don't re-add detail cards", it no
longer applies.

**Layout, as of 2026-09-01 (historical — see the 2026-10-05 note above):** the summary table at
the top carries all nine totals — this is the primary output. Below it,
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

**GCP invoice (user, 2026-10-05):** also run `bigquery-sql/gcp_invoice.sql`
(for a specific month, replace `FORMAT_DATE('%Y%m', CURRENT_DATE('US/Pacific'))`
with the literal `'YYYYMM'`). It reproduces Google's monthly invoice exactly
(Sept 2026: USD 40,424.12): grouped by `invoice.month`, all cost types,
seller = Google only. Add two top-level summary rows **above** GCP All
services: "GCP Invoice (Google)" and "GCP Marketplace (invoiced separately)"
(sum of the Marketplace sellers). Then make the **first** detail card "GCP —
<Month> invoice": a by-seller table plus a reconciliation table — GCP All
services (usage dates, after credits) + late-reported usage billed on the
invoice = invoice-month total, minus each Marketplace seller and rounding =
the Google invoice. Assert the reconciliation lands on the invoice figure to
the cent, and explain in the caption why the usage rows don't match it.

**All Production Costs (user, 2026-10-05):** also run
`bigquery-sql/gcp_all_production.sql` — the 24 platform service IDs across all
8 production projects (UK, US, orbit, data science). It is the **first**
sub-row under GCP All services ("GCP All Production Costs", Cost before
credits; Sept 2026 USD 17,026.39) and gets its own card right after the GCP
all-services card. It includes UK and US Platform COGS but not UK R&D or the
Speech API rows; the caption must say so.

**All Development Costs (user, 2026-10-05):** also run
`bigquery-sql/gcp_all_development.sql` — **every** service (no service.id
filter) across the 4 development projects (`prj-ufonia-dev-lon-svc-01`,
`prj-ufonia-dev-host-01`, `prj-ufonia-dev-iowa-svc-02`,
`prj-ufonia-dev-iowa-host-01`). Second sub-row under GCP All services, right
after All Production Costs ("GCP All Development Costs", Cost before
credits; Sept 2026 USD 8,139.41), with its own card after the All Production
card. It includes UK R&D Platform COGS and UK R&D API COGS. Note in the
caption that Production is platform services only while Development is all
services, so the two aren't like-for-like.

**Single Cost column (user, 2026-10-05) — supersedes the five-column
layout described in step 3a:** the summary table has just **Source | Cost**.
GCP All services shows its **Subtotal** (after credits) as its Cost. The five
GCP COGS rows show **Cost before credits** (the query's `Cost` column) —
COGS is reported on that basis and it matches the Billing console (Sept 2026
UK Platform COGS USD 13,001.11). AWS = UnblendedCost, Vonage = summed EUR
price. No Subtotal, Negotiated savings, Savings programmes or Other savings
columns anywhere, including the detail cards: the GCP all-services card lists
each service's Subtotal as "cost after credits"; the COGS cards list each
service's Cost as "cost before credits", sorted and charted on that value.
The caption must say which basis each row uses.

**Time zones (user, 2026-10-05):** the six GCP queries use **US/Pacific**
month boundaries (`CURRENT_DATE('US/Pacific')`, `TIMESTAMP(..., 'US/Pacific')`)
so they match the GCP Billing console and invoice — e.g. September 2026 UK
Platform COGS Cost is USD 13,001.11 on both. AWS and Vonage stay on
Europe/London dates. To run a specific month, pin the bounds in a scratchpad
copy of each file (GCP: replace the `CURRENT_DATE('US/Pacific')` expressions;
AWS/Vonage: the `CURRENT_DATE('Europe/London')` ones), and say on the page
which time zone each source uses. When the user compares a figure with the
console, compare it with the **Cost** column (before credits): console
exports leave the credit lists blank, so their Subtotal equals Cost.

## Steps

1. **Run all nine queries** against `prj-ufonia-cmn-lon-billing-01`, one
   `bq query --use_legacy_sql=false --project_id=prj-ufonia-cmn-lon-billing-01`
   call per file:
   - `bigquery-sql/gcp_all_services.sql`
   - `bigquery-sql/gcp_uk_api_cogs.sql`
   - `bigquery-sql/gcp_uk_platform_cogs.sql`
   - `bigquery-sql/gcp_us_platform_cogs.sql`
   - `` bigquery-sql/gcp_uk_r&d_platform_cogs.sql ``
   - `` bigquery-sql/gcp_uk_r&d_api_cogs.sql ``
   - `bigquery-sql/aws_services.sql`
   - `bigquery-sql/aws_services_by_environment.sql`
   - `bigquery-sql/vonage_services.sql`

   These can run in parallel (independent Bash calls in one message — quote
   filenames containing `&`, e.g. `"bigquery-sql/gcp_uk_r&d_platform_cogs.sql"`
   and `"bigquery-sql/gcp_uk_r&d_api_cogs.sql"`, since `&` is a shell
   metacharacter). All nine are needed even though only two get their own
   chart — the summary table (step 3a) uses every one of them.

   `gcp_all_services.sql`, `gcp_uk_platform_cogs.sql`, `gcp_us_platform_cogs.sql`,
   `` gcp_uk_r&d_platform_cogs.sql ``,
   and `aws_services.sql` are all capped
   at `LIMIT 10`, so for the summary table also run each one's
   un-limited equivalent (same CTE/filters, drop the `LIMIT 10` and the
   `GROUP BY`, just `SUM(...)` everything into one row) to get the true
   month-to-date total for each — the limited results understate the total
   once there are more than 10 services in scope. `gcp_uk_api_cogs.sql`,
   `` gcp_uk_r&d_api_cogs.sql ``, `vonage_services.sql`, and
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

1a-2. **`` gcp_uk_r&d_platform_cogs.sql `` is a same-shape sibling of `gcp_uk_platform_cogs.sql`**,
   not a subset/superset relationship the way API COGS and Platform COGS are.
   History: until 2026-09-01, `gcp_uk_platform_cogs.sql` itself scoped to 8
   dev/staging/trial projects; the user then corrected it to scope to the
   two actual production projects (`prj-ufonia-prd-lon-host-01`,
   `prj-ufonia-prd-lon-svc-01` — same two as `gcp_uk_api_cogs.sql`). ``
   gcp_uk_r&d_platform_cogs.sql `` started as an unmodified copy of the file
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

1a-2b. **`gcp_us_platform_cogs.sql` is another same-shape sibling of
   `gcp_uk_platform_cogs.sql`** (added 2026-10-05): same 24 service IDs, scoped
   to the single US production project `prj-ufonia-prd-iowa-svc-02`
   ("Dora Advanced Production", 736494139432). The user supplied it as a
   raw console export, which carried the 5 IDs removed from Platform COGS in
   August (see README Known issues); those were dropped to match, with no
   effect on totals. Disjoint project scope, never additive with Platform
   COGS. September 2026: 18 of 24 IDs matched, subtotal USD 1,993.22. Summary
   table sub-row only, no chart card.

1a-3. **`` gcp_uk_r&d_api_cogs.sql `` is the same relationship, one level down**:
   a copy of `gcp_uk_api_cogs.sql` (same single service ID, `63DE-82AB-F564`
   Cloud Speech API) re-scoped to the same 2 dev projects as ``
   gcp_uk_r&d_platform_cogs.sql `` (`prj-ufonia-dev-host-01`,
   `prj-ufonia-dev-lon-svc-01`) instead of `gcp_uk_api_cogs.sql`'s 2 production
   projects. Added 2026-09-01. Typically returns exactly 1 row and a very
   small figure (August 2026: USD 0.0072) — de minimis dev usage, not zero, so
   render it as a stat tile (per step 3), not "no matching rows". Disjoint
   project scope from `gcp_uk_api_cogs.sql`, never additive with it. **No longer
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
   - `sub-row`: ↳ GCP UK Platform COGS (gcp_uk_platform_cogs.sql)
   - `sub-row`: ↳ GCP US Platform COGS (gcp_us_platform_cogs.sql)
   - `sub-row`: ↳ GCP UK R&D Platform COGS (`` gcp_uk_r&d_platform_cogs.sql ``)
   - `sub-row`: ↳ GCP UK API COGS (gcp_uk_api_cogs.sql)
   - `sub-row`: ↳ GCP UK R&D API COGS (`` gcp_uk_r&d_api_cogs.sql ``)
   - AWS All services (aws_services.sql)
   - `sub-row`: ↳ AWS Development (aws_services_by_environment.sql)
   - `sub-row`: ↳ AWS Production (aws_services_by_environment.sql)
   - Vonage all categories (vonage_services.sql)
   - `sub-row`: ↳ Vonage SMS
   - `sub-row`: ↳ Vonage Inbound Calls
   - `sub-row`: ↳ Vonage Outbound Calls
   - `sub-row`: ↳ Vonage WebSocket
   - `sub-row`: ↳ Vonage Other

   **Vonage sub-rows (user, 2026-10-05):** one per `vonage_services.sql`
   category, in the order above (not sorted by cost), in EUR, savings columns
   0. Like the AWS sub-rows they **sum exactly** to the Vonage parent row, so
   the caption must group them with AWS as the decomposing case. The Vonage
   bar chart card below stays as well.

   **Full Vonage breakdown (user, 2026-10-05):** the Vonage card's table is
   open by default (`<details open>`) and rendered as static HTML, one row
   per category × `product` × `direction` with record counts and a total
   row. Get it with an extra query on the same table and date window:
   `SELECT category, product, direction, COUNT(*) n, ROUND(SUM(total_price),2)
   cost ... GROUP BY 1,2,3`. Check its total and record count match
   `vonage_services.sql` and the table's full row count, and say in the
   caveat that nothing is unallocated (or flag any null/unexpected category).

   **Display labels (user, 2026-10-05):** the rows for `gcp_uk_platform_cogs.sql`
   and `gcp_uk_api_cogs.sql` are labelled "UK Platform COGS" and "UK API COGS"
   (in the table and caption) to distinguish them from US Platform COGS. The
   files themselves were renamed from `gcp_platform_cogs.sql` /
   `gcp_api_cogs.sql` on 2026-10-05. Likewise the R&D rows are labelled
   "UK R&D Platform COGS" and "UK R&D API COGS", and their files were renamed
   from `gcp_r&d_platform_cogs.sql` / `gcp_r&d_api_cogs.sql` the same day.

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
   - Under **GCP All services**, the five sub-rows (Platform COGS, US
     Platform COGS, R&D Platform COGS, API COGS, R&D API COGS) **do not sum** to the parent, nor
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
     category (typically "Other"/VOICE-TTS) returns 0 or is missing
     entirely, that's expected — say so rather than treating it as an
     error.
   - `gcp_uk_api_cogs.sql` (summary row only): flag any `service.id` filter
     value that appears in the
     query's WHERE clause but not in the returned rows (e.g. the unresolved
     `02DA-B362-D983` — check README's Known issues for current status) — put
     this caveat in the summary caption since there's no dedicated card for
     it any more.
   - `gcp_uk_platform_cogs.sql` (summary row only): same check — as of the
     2026-09-01 project-scope
     correction, 23 of 24 service IDs match at least one row against the new
     2-project production scope; `82AF-DE7A-51D0` (Container Registry
     Vulnerability Scanning) is valid but had zero usage there last month
     (see README's Known issues) — re-derive this each run rather than
     assuming it's still true.
   - `` gcp_uk_r&d_platform_cogs.sql `` (summary row only): note explicitly
     that despite the "R&D"
     label being informal (not an official GCP/billing-console term), this
     query's 2-project scope (`prj-ufonia-dev-host-01`,
     `prj-ufonia-dev-lon-svc-01`) descends from what `gcp_uk_platform_cogs.sql`
     itself used to cover (8 dev/staging/trial projects) before the
     2026-09-01 correction, then was narrowed further the same day. All 24
     service IDs matched at least one row against this 2-project scope as of
     August 2026 (see README) — re-derive this each run rather than assuming
     it stays true.
   - `` gcp_uk_r&d_api_cogs.sql `` (summary row only, chart card removed
     2026-09-01): same query/service as
     `gcp_uk_api_cogs.sql`,
     disjoint project scope (2 dev projects — see step 1a-3). Normally 1 row
     with a very small figure (August 2026: USD 0.0072) — de minimis usage, not
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
