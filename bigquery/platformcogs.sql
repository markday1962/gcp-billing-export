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
  AND (project.id IN ('429341992774',
      '616882422931',
      '755278750337',
      '728785948359',
      '446749836522',
      '1077743477878',
      '436127040239',
      '1065587544')
    OR project.number IN ('429341992774',
      '616882422931',
      '755278750337',
      '728785948359',
      '446749836522',
      '1077743477878',
      '436127040239',
      '1065587544'))
  AND usage_start_time >= TIMESTAMP(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), 'Europe/London')
  AND usage_start_time < TIMESTAMP(DATE_ADD(DATE_TRUNC(CURRENT_DATE('Europe/London'), MONTH), INTERVAL 1 MONTH), 'Europe/London')
  AND service.id IN ('F17B-412E-CB64',
    '149C-F9EC-3994',
    '24E6-581D-38E5',
    'DCC9-8DB9-673F',
    '7766-403C-6D6E',
    'D64E-AF12-1813',
    'FA26-5236-B8B5',
    'D870-408D-92A6',
    '7C52-19D8-71EE',
    '5490-F7B7-8DF6',
    '5AF5-2C11-D467',
    '58CD-E7C3-72CA',
    'A1E8-BE35-7EBC',
    '152E-C115-5142',
    '9662-B51E-5089',
    '95FF-2EF5-5EA1',
    '9B82-7513-9D1C',
    '6F81-5844-456A',
    '82AF-DE7A-51D0',
    '7EC6-CE53-9E39',
    'C5E6-A27F-6A44',
    'DC5D-D207-FD2F',
    'CCD8-9BF1-090E',
    'E505-1604-58F8',
    'EE82-7A5E-871C',
    'FBF2-FC68-171A',
    '2062-016F-44A2',
    '1DB1-3CD3-35A3',
    'C7E2-9256-1C43') )
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
