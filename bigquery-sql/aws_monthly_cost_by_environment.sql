-- AWS cost split by environment (Production vs Development) for the previous
-- calendar month (Europe/London), from the CUR-to-BigQuery import pipeline
-- (see aws-bigquery-loader/README.md). Same
-- CURRENT_DATE-relative pattern as aws_monthly_cost.sql, shifted back one
-- month -- for the current calendar month instead, see
-- aws_services_by_environment.sql.
--
-- Uses the CUR's cost_category_production / cost_category_development
-- columns (an AWS Cost Category configured on this account) rather than
-- line_item_usage_account_id -- the payer account (453829601976) has 15
-- linked member accounts, none individually named "production" or
-- "development", so the Cost Category is the only clean prod/dev split
-- available here. Any line item matching neither category falls into
-- "Uncategorized" rather than being silently dropped -- as of 2026-08 every
-- row matched one or the other, but that isn't guaranteed to stay true.
--
-- Excludes AWS Marketplace charges (third-party products such as the
-- "(Amazon Bedrock Edition)" Claude/OpenAI models). They're identified by
-- line_item_product_code being a random-looking Marketplace product ID
-- (20+ lowercase letters/digits) rather than an AWS code like AmazonEC2.
-- See aws_marketplace.sql for those charges.
--
-- Includes VAT (line_item_type = 'Tax' rows) since 2026-10-05, so figures
-- match the AWS console; AWS charges 20% UK VAT on its own services, and
-- the Marketplace products here carry none.
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
  NOT REGEXP_CONTAINS(line_item_product_code, r'^[a-z0-9]{20,}$')
  AND usage_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE('Europe/London'), INTERVAL 1 MONTH), MONTH)
  AND usage_date < DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
GROUP BY
  Environment
ORDER BY
  Cost DESC
