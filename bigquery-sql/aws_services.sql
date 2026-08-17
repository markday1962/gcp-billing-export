-- AWS cost by service for the current calendar month, from the
-- CUR-to-BigQuery import pipeline (see aws-bigquery-ingress/README.md). Excludes
-- line_item_type = 'Tax', to match the GCP queries' exclusion of
-- tax/adjustment rows. Mirrors bigquery-sql/services.sql's shape/window so the
-- two can sit side by side in the billing dashboard.
SELECT
  product_name AS `Service Description`,
  ROUND(SUM(line_item_unblended_cost), 2) AS `Cost`
FROM
  `prj-ufonia-cmn-lon-billing-01.bg_dataset_aws_cost_and_usage.aws_cost_and_usage`
WHERE
  line_item_type != 'Tax'
  AND usage_date >= DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
  AND usage_date < DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH)
GROUP BY
  product_name
ORDER BY
  Cost DESC
LIMIT 10
