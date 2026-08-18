-- AWS cost by service for the previous calendar month (Europe/London), from
-- the CUR-to-BigQuery import pipeline (see aws-bigquery-loader/README.md). Excludes
-- line_item_type = 'Tax', to match the GCP queries' exclusion of
-- tax/adjustment rows. Same CURRENT_DATE-relative pattern as
-- bigquery-sql/services.sql, shifted back one month — for the current calendar
-- month instead, see bigquery-sql/aws_services.sql.
--
-- NOTE: as of 2026-08-17 the table only contains data from 2026-08-01
-- onward (the CUR export started this month) — this query returns zero
-- rows until a full previous month's data exists.
SELECT
  product_name AS `Service`,
  ROUND(SUM(line_item_unblended_cost), 2) AS `Cost`
FROM
  `prj-ufonia-cmn-lon-billing-01.bg_dataset_aws_cost_and_usage.aws_cost_and_usage`
WHERE
  line_item_type != 'Tax'
  AND usage_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE('Europe/London'), INTERVAL 1 MONTH), MONTH)
  AND usage_date < DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
GROUP BY
  product_name
ORDER BY
  Cost DESC
LIMIT 10
