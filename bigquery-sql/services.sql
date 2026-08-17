-- Costs take a few hours to show up in your BigQuery export,and might take longer than 24 hours.
-- To send feedback about this query,click Help, and select Send feedback.
WITH
cost_data AS (
SELECT
  *,
  0 AS `spend_cud_fee_cost`,
  cost - IFNULL(cost_at_effective_price_default, cost) AS `spend_cud_savings`,
  IFNULL(cost_at_effective_price_default, cost) - cost_at_list AS `negotiated_savings`,
  IFNULL( (
    SELECT
      SUM(CAST(c.amount AS NUMERIC))
    FROM
      UNNEST(credits) c
    WHERE
      c.type IN ('COMMITTED_USAGE_DISCOUNT',
        'COMMITTED_USAGE_DISCOUNT_DOLLAR_BASE',
        'FEE_UTILIZATION_OFFSET')), 0) AS `cud_credits`,
  IFNULL( (
    SELECT
      SUM(CAST(c.amount AS NUMERIC))
    FROM
      UNNEST(credits) c
    WHERE
      c.type IN ('CREDIT_TYPE_UNSPECIFIED',
        'PROMOTION',
        'SUSTAINED_USAGE_DISCOUNT',
        'DISCOUNT',
        'FREE_TIER',
        'SUBSCRIPTION_BENEFIT',
        'RESELLER_MARGIN')), 0) AS `other_savings`
FROM
  `prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_billing_export_resource_v1_0194CA_24F6D5_7ED48D`
WHERE
  cost_type != 'tax'
  AND cost_type != 'adjustment'
  AND usage_start_time >= TIMESTAMP(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), 'Europe/London')
  AND usage_start_time < TIMESTAMP(DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH), 'Europe/London') )
SELECT
service.description AS `Service Description`,
SUM(CAST(cost_at_list AS NUMERIC)) - SUM(CAST(spend_cud_fee_cost AS NUMERIC)) AS `Cost`,
SUM(CAST(negotiated_savings AS NUMERIC)) AS `Negotiated savings`,
SUM(CAST(spend_cud_fee_cost AS NUMERIC)) + SUM(CAST(spend_cud_savings AS NUMERIC)) + SUM(CAST(cud_credits AS NUMERIC)) AS `Savings programmes`,
SUM(CAST(other_savings AS NUMERIC)) AS `Other savings`,
SUM(CAST(cost AS NUMERIC)) + SUM(CAST(cud_credits AS NUMERIC)) + SUM(CAST(other_savings AS NUMERIC)) AS `Subtotal`
FROM
cost_data
GROUP BY
service.description
ORDER BY
Subtotal DESC
LIMIT 10
