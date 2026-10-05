-- AWS cost by service for the current calendar month, from the
-- CUR-to-BigQuery import pipeline (see aws-bigquery-loader/README.md). Mirrors bigquery-sql/gcp_all_services.sql's shape/window so the
-- two can sit side by side in the billing dashboard.
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
  product_name AS `Service Description`,
  ROUND(SUM(line_item_unblended_cost), 2) AS `Cost`
FROM
  `prj-ufonia-cmn-lon-billing-01.bg_dataset_aws_cost_and_usage.aws_cost_and_usage`
WHERE
  NOT REGEXP_CONTAINS(line_item_product_code, r'^[a-z0-9]{20,}$')
  AND usage_date >= DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
  AND usage_date < DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH)
GROUP BY
  product_name
ORDER BY
  Cost DESC
LIMIT 10
