-- GCP invoice total for the current invoice month, reproducing the monthly
-- Google Cloud invoice (e.g. September 2026: $40,424.12 for seller Google).
--
-- Differs from gcp_all_services.sql in three ways, matching how Google
-- builds the invoice:
--   * Groups by invoice.month, not usage_start_time -- late-reported usage
--     from the end of the previous month lands on this month's invoice.
--   * Keeps every cost_type (regular, tax, adjustment, rounding_error),
--     since the invoice includes tax and adjustments.
--   * Splits by seller: only seller_name = 'Google' is on Google's own
--     invoice. Marketplace sellers (e.g. 84codes AB for CloudAMQP,
--     Elasticsearch B.V. for Elastic Cloud) are billed through the same
--     billing account but invoiced separately.
--
-- `Credits` is every credit type (sustained use, discounts, promotions,
-- subscription benefits, CUDs). `Total` = Cost + Credits.
SELECT
  CASE
    WHEN seller_name = 'Google' THEN 'Google invoice'
    WHEN seller_name IS NULL THEN 'Unattributed (rounding)'
    ELSE 'Marketplace (invoiced separately)'
  END AS `Invoice`,
  IFNULL(seller_name, '-') AS `Seller`,
  ROUND(SUM(cost), 2) AS `Cost`,
  ROUND(SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS `Credits`,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS `Total`
FROM
  `prj-ufonia-cmn-lon-billing-01.bq_dataset_billing_ufonia_invoice.gcp_billing_export_resource_v1_0194CA_24F6D5_7ED48D`
WHERE
  invoice.month = FORMAT_DATE('%Y%m', CURRENT_DATE('US/Pacific'))
GROUP BY
  `Invoice`,
  `Seller`
ORDER BY
  `Invoice`,
  `Total` DESC
