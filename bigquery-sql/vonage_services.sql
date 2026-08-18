-- Vonage cost by category for the current calendar month (Europe/London),
-- from the Reports API import pipeline (see vonage-bigquery-loader/README.md).
-- Mirrors bigquery-sql/aws_services.sql's shape/window so all three sources
-- can sit side by side in the billing dashboard.
--
-- CAVEAT: every SMS row's `currency` field comes back blank from Vonage's
-- Reports API on this account (a data quirk, not a pipeline bug) - the
-- Cost figure below sums total_price regardless of currency, so treat it
-- as EUR to match every other category rather than a confirmed figure.
SELECT
  category AS `Service Description`,
  ROUND(SUM(total_price), 2) AS `Cost`
FROM
  `prj-ufonia-cmn-lon-billing-01.bq_dataset_vonage_cost_and_usage.vonage_cost_and_usage`
WHERE
  usage_date >= DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH)
  AND usage_date < DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH)
GROUP BY
  category
ORDER BY
  Cost DESC
