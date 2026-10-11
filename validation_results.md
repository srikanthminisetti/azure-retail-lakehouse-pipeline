# Validation results

These results were produced by running the three notebooks in a Microsoft Fabric workspace. Every number below is taken from the
notebooks' own validation output (Bronze check, Silver reconciliation, quarantine summary, Gold checks). The notebooks stop with an
assertion if any check fails, so a successful run means every check passed.

> The expected values (`manifest.json`) come from the local batch-preparation script, which computes them from the original data
> *independently of the notebooks*. The quarantined counts equal the injected bad rows **by design** — they show that the rules catch
> the issues that were planted, not that the real-world data has no other problems.

## 1. Bronze (`nb_01_bronze_ingestion`) — row and file counts vs. manifest

| Table | Manifest rows | Bronze rows | Batch files | Status |
|---|---:|---:|---:|---|
| orders | 136,570 | 136,570 | 26 | OK |
| customers | 99,938 | 99,938 | 1 | OK |
| order_items | 113,796 | 113,796 | 24 | OK |
| order_payments | 104,945 | 104,945 | 25 | OK |
| order_reviews | 100,236 | 100,236 | 23 | OK |
| products | 32,951 | 32,951 | 1 | OK |
| sellers | 3,095 | 3,095 | 1 | OK |
| geolocation | 1,000,163 | 1,000,163 | 1 | OK |
| category_translation | 71 | 71 | 1 | OK |

Total: 103 batch files (26 + 24 + 25 + 23 + 5 single-file tables) and 1,591,765 Bronze rows. No row had a missing `_batch_date`.

## 2. Silver (`nb_02_silver_transformation`) — reconciliation

`Bronze rows = Silver rows + quarantined rows + duplicates / superseded versions removed`, and Silver business keys are unique.

| Table | Bronze | Silver | Quarantined | Removed | Manifest expected Silver |
|---|---:|---:|---:|---:|---:|
| orders | 136,570 | 99,441 | 20 | 37,109 | 99,441 |
| customers | 99,938 | 99,441 | 0 | 497 | 99,441 |
| order_items | 113,796 | 112,650 | 20 | 1,126 | 112,650 |
| order_payments | 104,945 | 103,886 | 20 | 1,039 | 103,886 |
| order_reviews | 100,236 | 99,224 | 20 | 992 | 99,224 |
| products | 32,951 | 32,951 | 0 | 0 | 32,951 |
| sellers | 3,095 | 3,095 | 0 | 0 | 3,095 |
| category_translation | 71 | 71 | 0 | 0 | 71 |
| geolocation | 1,000,163 | 738,332 | 0 | 261,831 | 738,332 |

For `orders`, "removed" are older versions of the same order (early *processing* snapshots) and re-delivered copies; the latest batch wins.

### Quarantine summary (rule → rows)

| Table | Rule | Rows |
|---|---|---:|
| orders | `customer_id_present` | 7 |
| orders | `order_status_valid` | 7 |
| orders | `delivery_not_before_purchase` | 6 |
| order_items | `price_non_negative` | 10 |
| order_items | `freight_non_negative` | 10 |
| order_payments | `payment_type_valid` | 10 |
| order_payments | `payment_value_non_negative` | 10 |
| order_reviews | `review_score_between_1_and_5` | 20 |

## 3. Gold (`nb_03_silver_to_gold`)

| Table | Rows |
|---|---:|
| gold_dim_date | 774 |
| gold_dim_customer | 96,096 |
| gold_dim_product | 32,951 |
| gold_dim_seller | 3,095 |
| gold_fact_orders | 99,441 |
| gold_fact_order_items | 112,650 |
| gold_daily_sales | 614 |
| gold_payment_method_performance | 4 |
| gold_product_category_sales | 74 |
| gold_customer_summary | 94,983 |
| gold_delivery_performance | 556 |

**Validation checks: 19 of 19 passed.**

| Check | Actual | Expected |
|---|---:|---:|
| fact_orders rows = silver_orders | 99,441 | 99,441 |
| fact_orders unique order_id | 99,441 | 99,441 |
| fact_orders orders without a customer | 0 | 0 |
| fact_order_items rows = silver_order_items | 112,650 | 112,650 |
| fact_order_items unique (order_id, order_item_id) | 112,650 | 112,650 |
| fact_order_items total price = silver total price | 13,591,643.70 | 13,591,643.70 |
| fact_orders items_value = silver total price | 13,591,643.70 | 13,591,643.70 |
| fact_orders payment_value = silver total payments | 16,008,872.12 | 16,008,872.12 |
| dim_customer rows = distinct customer_unique_id | 96,096 | 96,096 |
| dim_product rows = silver_products | 32,951 | 32,951 |
| dim_seller rows = silver_sellers | 3,095 | 3,095 |
| orders with a date missing in dim_date | 0 | 0 |
| daily_sales GMV = fact GMV (revenue orders) | 13,494,400.74 | 13,494,400.74 |
| daily_sales orders = distinct revenue orders with items | 98,199 | 98,199 |
| category sales revenue = fact GMV | 13,494,400.74 | 13,494,400.74 |
| customer_summary spent = fact GMV | 13,494,400.74 | 13,494,400.74 |
| customer_summary orders = distinct revenue orders with items | 98,199 | 98,199 |
| payment mart value = payments of revenue orders | 15,739,137.01 | 15,739,137.01 |
| delivery_performance orders = delivered orders | 96,470 | 96,470 |

### Data observations (reported, deliberately not forced to any value)

| Observation | Count |
|---|---:|
| Orders where payments differ from items + freight by more than 1.00 | 249 |
| Orders marked `delivered` without a delivery date | 8 |
| Orders with more than one review | 547 |
| Revenue orders without items | 8 |
| Products whose category has no English translation | 13 |
| Products with no category in the source | 610 |
