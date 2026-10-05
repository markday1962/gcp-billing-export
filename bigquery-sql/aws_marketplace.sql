-- AWS Marketplace charges for the current calendar month (Europe/London),
-- from the CUR-to-BigQuery import (see aws-bigquery-loader/README.md).
-- Marketplace products are third-party products billed through AWS, e.g.
-- the "(Amazon Bedrock Edition)" Claude and OpenAI models. They're
-- identified by line_item_product_code being a Marketplace product ID (20+
-- lowercase letters/digits) rather than an AWS service code like AmazonEC2.
-- aws_services.sql and aws_services_by_environment.sql exclude these rows.
--
-- Includes VAT (line_item_type = 'Tax' rows) since 2026-10-05, so figures
-- match the AWS console; AWS charges 20% UK VAT on its own services, and
-- the Marketplace products here carry none.
SELECT
  product_name AS `Service Description`,
  CASE
    WHEN cost_category_production = 'Production' THEN 'Production'
    WHEN cost_category_development = 'Development' THEN 'Development'
    ELSE 'Uncategorized'
  END AS `Environment`,
  ROUND(SUM(line_item_unblended_cost), 2) AS `Cost`
FROM
  `prj-ufonia-cmn-lon-billing-01.bg_dataset_aws_cost_and_usage.aws_cost_and_usage`
WHERE
  REGEXP_CONTAINS(line_item_product_code, r'^[a-z0-9]{20,}$')
  AND usage_date >= DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
  AND usage_date < DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH)
GROUP BY
  `Service Description`,
  `Environment`
ORDER BY
  `Cost` DESC
