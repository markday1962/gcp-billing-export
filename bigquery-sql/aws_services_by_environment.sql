-- AWS cost split by environment (Production vs Development) for the current
-- calendar month, from the CUR-to-BigQuery import pipeline (see
-- aws-bigquery-loader/README.md). Excludes line_item_type = 'Tax', matching
-- aws_services.sql.
--
-- Uses the CUR's cost_category_production / cost_category_development
-- columns (an AWS Cost Category configured on this account) rather than
-- line_item_usage_account_id -- the payer account (453829601976) has 15
-- linked member accounts, none individually named "production" or
-- "development", so the Cost Category is the only clean prod/dev split
-- available here. Any line item matching neither category falls into
-- "Uncategorized" rather than being silently dropped -- as of 2026-08 every
-- row matched one or the other, but that isn't guaranteed to stay true.
SELECT
  CASE
    WHEN cost_category_production = 'Production' THEN 'Production'
    WHEN cost_category_development = 'Development' THEN 'Development'
    ELSE 'Uncategorized'
  END AS `Environment`,
  ROUND(SUM(line_item_unblended_cost), 2) AS `Cost`
FROM
  `prj-ufonia-cmn-lon-billing-01.bg_dataset_aws_cost_and_usage.aws_cost_and_usage`
WHERE
  line_item_type != 'Tax'
  AND usage_date >= DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
  AND usage_date < DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH)
GROUP BY
  Environment
ORDER BY
  Cost DESC
