# SQL analytics on the Gold layer

**File:** [`sql/gold_analytics_queries.sql`](../SQL/gold_analytics_queries.sql) — 12 T-SQL queries (Q0–Q11) over the `gold_*` tables.

> **Status:** Q1–Q11 were **executed on the Fabric SQL analytics endpoint** and their outputs are recorded below. Q0 (row-count sanity
> check) is in the query file, but its output was not recorded. Before execution, the query logic was tested on a local copy of the
> Gold tables.

## Why the SQL analytics endpoint

Every Fabric Lakehouse automatically gets a **SQL analytics endpoint**: a **read-only T-SQL** surface over its Delta tables. The Gold tables
written by `nb_03_silver_to_gold` therefore become queryable with plain T-SQL, without moving data. Notes that matter in practice:

- It is read-only for tables (no `INSERT` / `UPDATE` / `DELETE`); views and functions can be created.
- The endpoint syncs lakehouse metadata automatically with a short delay. If a `gold_*` table is missing, click **Refresh** in the endpoint's Explorer toolbar.
- Delta `boolean` columns appear as `bit`, so filters use `= 1` / `= 0`.
- String comparisons are case-sensitive; all source status values are lower case.

Sources: <https://learn.microsoft.com/fabric/data-engineering/lakehouse-sql-analytics-endpoint>, <https://learn.microsoft.com/fabric/data-engineering/sql-analytics-endpoint-metadata-sync>

## How to run

1. Open the Lakehouse and switch to the **SQL analytics endpoint**.
2. **New SQL query**, paste the contents of `sql/gold_analytics_queries.sql`.
3. Select **one query at a time** (from its `-- Qn` comment to its `;`) and click **Run**.
4. Start with **Q0**: every row must show `row_count = expected_rows`.

## Query catalogue

| Query | Business question | Gold tables | Techniques |
|---|---|---|---|
| Q0 | Is every Gold table present and complete? | all 11 | `UNION ALL`, expected-count check |
| Q1 | How big is the business and how well does it deliver? | daily_sales, customer_summary, fact_orders | scalar subqueries, conditional aggregation |
| Q2 | How are sales trending month over month? | daily_sales, dim_date | CTEs, `LAG`, fact-to-dimension join, guard against tiny months |
| Q3 | Which categories earn the most? | product_category_sales | `RANK`, `SUM() OVER ()` share of total, `TOP` |
| Q4 | How concentrated is revenue (80% rule)? | product_category_sales | CTEs, `ROW_NUMBER`, running total (`ROWS BETWEEN …`) |
| Q5 | How do customers pay? | payment_method_performance | formatting stored ratios |
| Q6 | How many customers return, and what do they bring? | customer_summary | conditional aggregation |
| Q7 | How recent are customers, and what are they worth? | customer_summary | `CASE` bucketing in a derived table |
| Q8 | Which states have the weakest on-time delivery? | fact_orders | `GROUP BY` / `HAVING`, exact averages at order grain |
| Q9 | Does late delivery hurt review scores? | fact_orders | `CASE` buckets on delay, share of low scores |
| Q10 | Is delivery performance improving over time? | delivery_performance | `HAVING` to drop tiny months |
| Q11 | Which sellers matter most and how good is their service? | fact_order_items, dim_seller | fact-to-dimension join, nested `CASE` in `AVG` |

## Design notes (worth being able to explain)

- **Revenue orders only** in sales queries (status not `canceled` / `unavailable`); GMV is item price, freight is shown separately.
- **Guards against misleading numbers.** Q2 shows growth only when both months have at least 100 orders, because the first (2016) and last (2018-09/10) months of the dataset are tiny partial months. Q10 drops months with fewer than 100 delivered orders. Q8 requires at least 500 delivered orders per state.
- **Mart vs. fact.** Q5, Q10 use the pre-aggregated analytics tables (counts and sums, so the results are exact). Q8, Q9 and Q11 read the order- or item-grain facts when an exact average or a new grouping is needed.
- **Recency (Q7)** is measured from the last order date in the data, not from today, because the dataset is historical.
- **Review scores** are the latest review per order; category and seller averages are item-weighted.
- **Decimals.** Percentages use `100.0 * a / b` with an explicit `CAST(... AS DECIMAL(p,s))`, which avoids integer division and gives fixed precision.

## Results from the SQL analytics endpoint

### Q1 — Headline KPIs

| total_gmv | total_freight | revenue_orders | customers | avg_order_value | delivered_orders | on_time_pct |
|---|---|---|---|---|---|---|
| 13494400.74 | 2241126.29 | 98199 | 94983 | 137.42 | 96470 | 93.23 |

![Q1 on the SQL analytics endpoint](../screenshots/sql_q1_headline_kpis.png)

### Q2 — Monthly sales trend with month-over-month growth

Growth is shown only when both months have at least 100 orders (`NULL` otherwise).

| year_month | orders | gmv | freight | avg_order_value | gmv_mom_pct |
|---|---|---|---|---|---|
| 2016-09 | 2 | 207.86 | 71.83 | 103.93 | NULL |
| 2016-10 | 290 | 44507.30 | 6847.22 | 153.47 | NULL |
| 2016-12 | 1 | 10.90 | 8.72 | 10.90 | NULL |
| 2017-01 | 787 | 120098.27 | 16845.19 | 152.60 | NULL |
| 2017-02 | 1718 | 244959.35 | 38602.34 | 142.58 | 104.0 |
| 2017-03 | 2617 | 368341.32 | 57276.64 | 140.75 | 50.4 |
| 2017-04 | 2377 | 353842.98 | 52005.63 | 148.86 | -3.9 |
| 2017-05 | 3640 | 503159.19 | 79551.64 | 138.23 | 42.2 |
| 2017-06 | 3205 | 429916.61 | 69735.63 | 134.14 | -14.6 |
| 2017-07 | 3946 | 492287.30 | 86466.43 | 124.76 | 14.5 |
| 2017-08 | 4272 | 568245.79 | 93657.73 | 133.02 | 15.4 |
| 2017-09 | 4227 | 621415.91 | 95686.81 | 147.01 | 9.4 |
| 2017-10 | 4547 | 660179.62 | 104576.41 | 145.19 | 6.2 |
| 2017-11 | 7421 | 1003862.14 | 168329.54 | 135.27 | 52.1 |
| 2017-12 | 5618 | 742183.79 | 119342.98 | 132.11 | -26.1 |
| 2018-01 | 7187 | 945456.29 | 156463.72 | 131.55 | 27.4 |
| 2018-02 | 6624 | 837895.43 | 141590.73 | 126.49 | -11.4 |
| 2018-03 | 7168 | 981051.06 | 171605.93 | 136.87 | 17.1 |
| 2018-04 | 6919 | 993592.98 | 162655.91 | 143.60 | 1.3 |
| 2018-05 | 6833 | 992871.75 | 152814.71 | 145.31 | -0.1 |
| 2018-06 | 6145 | 863265.53 | 157116.37 | 140.48 | -13.1 |
| 2018-07 | 6233 | 878044.27 | 161739.31 | 140.87 | 1.7 |
| 2018-08 | 6421 | 848860.10 | 148113.41 | 132.20 | -3.3 |
| 2018-09 | 1 | 145.00 | 21.46 | 145.00 | NULL |

### Q3 — Top 10 product categories by revenue

| revenue_rank | category | units_sold | orders | revenue | revenue_share_pct | avg_price | avg_review_score | late_delivery_pct |
|---|---|---|---|---|---|---|---|---|
| 1 | health_beauty | 9634 | 8800 | 1255695.13 | 9.31 | 130.34 | 4.15 | 7.56 |
| 2 | watches_gifts | 5970 | 5604 | 1198185.21 | 8.88 | 200.70 | 4.03 | 7.21 |
| 3 | bed_bath_table | 11097 | 9399 | 1035964.06 | 7.68 | 93.36 | 3.9 | 7.03 |
| 4 | sports_leisure | 8590 | 7673 | 979740.92 | 7.26 | 114.06 | 4.12 | 6.31 |
| 5 | computers_accessories | 7781 | 6654 | 904322.02 | 6.70 | 116.22 | 3.95 | 6.49 |
| 6 | furniture_decor | 8298 | 6425 | 727465.05 | 5.39 | 87.67 | 3.92 | 7.03 |
| 7 | housewares | 6915 | 5847 | 626825.80 | 4.65 | 90.65 | 4.07 | 5.00 |
| 8 | cool_stuff | 3779 | 3616 | 620770.49 | 4.60 | 164.27 | 4.16 | 5.84 |
| 9 | auto | 4204 | 3872 | 586585.73 | 4.35 | 139.53 | 4.08 | 7.03 |
| 10 | garden_tools | 4328 | 3505 | 481009.94 | 3.56 | 111.14 | 4.06 | 6.56 |

### Q4 — Categories that make up the first 80% of revenue

The 18th category brings the cumulative share to 81.26%, so 18 of the 74 categories make up the first 80% of revenue.

| category_rank | category | revenue | revenue_share_pct | cumulative_share_pct |
|---|---|---|---|---|
| 1 | health_beauty | 1255695.13 | 9.31 | 9.31 |
| 2 | watches_gifts | 1198185.21 | 8.88 | 18.18 |
| 3 | bed_bath_table | 1035964.06 | 7.68 | 25.86 |
| 4 | sports_leisure | 979740.92 | 7.26 | 33.12 |
| 5 | computers_accessories | 904322.02 | 6.70 | 39.82 |
| 6 | furniture_decor | 727465.05 | 5.39 | 45.21 |
| 7 | housewares | 626825.80 | 4.65 | 49.86 |
| 8 | cool_stuff | 620770.49 | 4.60 | 54.46 |
| 9 | auto | 586585.73 | 4.35 | 58.81 |
| 10 | garden_tools | 481009.94 | 3.56 | 62.37 |
| 11 | toys | 479808.54 | 3.56 | 65.93 |
| 12 | baby | 410312.20 | 3.04 | 68.97 |
| 13 | perfumery | 396599.31 | 2.94 | 71.91 |
| 14 | telephony | 322342.64 | 2.39 | 74.29 |
| 15 | office_furniture | 273580.70 | 2.03 | 76.32 |
| 16 | stationery | 229593.84 | 1.70 | 78.02 |
| 17 | computers | 222963.13 | 1.65 | 79.68 |
| 18 | pet_shop | 213766.63 | 1.58 | 81.26 |

### Q5 — Payment method mix

| payment_type | orders | payment_rows | payment_value | share_of_value_pct | avg_installments | avg_payment_value |
|---|---|---|---|---|---|---|
| credit_card | 75618 | 75905 | 12350042.56 | 78.47 | 3.51 | 162.70 |
| boleto | 19539 | 19539 | 2826802.30 | 17.96 | 1 | 144.67 |
| voucher | 3745 | 5613 | 349874.40 | 2.22 | 1 | 62.33 |
| debit_card | 1515 | 1516 | 212417.75 | 1.35 | 1 | 140.12 |

### Q6 — Repeat-customer rate

Customers are real people (`customer_unique_id`).

| customers | repeat_customers | repeat_customer_pct | repeat_revenue_pct | avg_spent_per_customer |
|---|---|---|---|---|
| 94983 | 2887 | 3.04 | 5.56 | 142.07 |

### Q7 — Customer recency segments

Recency is measured from the last order date in the data.

| recency_segment | customers | revenue | avg_spent | repeat_customers |
|---|---|---|---|---|
| 1. 0-90 days | 9463 | 1322707.61 | 139.78 | 307 |
| 2. 91-180 days | 18234 | 2687827.72 | 147.41 | 619 |
| 3. 181-365 days | 39344 | 5473841.55 | 139.13 | 1225 |
| 4. over 365 days | 27942 | 4010023.86 | 143.51 | 736 |

### Q8 — Ten weakest states for on-time delivery (at least 500 delivered orders)

| state | delivered_orders | avg_delivery_days | late_orders | on_time_pct |
|---|---|---|---|---|
| MA | 717 | 21.51 | 125 | 82.57 |
| CE | 1279 | 21.20 | 176 | 86.24 |
| BA | 3256 | 19.28 | 396 | 87.84 |
| RJ | 12350 | 15.24 | 1495 | 87.89 |
| PA | 946 | 23.73 | 106 | 88.79 |
| ES | 1995 | 15.72 | 214 | 89.27 |
| PB | 517 | 20.39 | 54 | 89.56 |
| MS | 701 | 15.54 | 68 | 90.30 |
| PE | 1593 | 18.40 | 153 | 90.40 |
| SC | 3546 | 14.90 | 291 | 91.79 |

### Q9 — Delivery delay vs. review score

Review score is the latest review of each delivered order; the buckets use `delivery_delay_days` (negative = early). 95,824 delivered orders have a review.

| delay_bucket | reviewed_orders | avg_review_score | low_score_pct |
|---|---|---|---|
| 1. 8+ days early | 70929 | 4.32 | 8.97 |
| 2. 1-7 days early | 17234 | 4.20 | 10.25 |
| 3. on the estimated date | 1280 | 4.03 | 12.42 |
| 4. 1-3 days late | 1852 | 3.29 | 32.13 |
| 5. 4-7 days late | 1748 | 2.10 | 67.62 |
| 6. 8+ days late | 2781 | 1.70 | 79.29 |

### Q10 — Monthly on-time delivery trend

Months with fewer than 100 delivered orders are excluded.

| order_month | delivered_orders | late_orders | on_time_pct |
|---|---|---|---|
| 2016-10 | 265 | 2 | 99.25 |
| 2017-01 | 750 | 22 | 97.07 |
| 2017-02 | 1653 | 49 | 97.04 |
| 2017-03 | 2546 | 116 | 95.44 |
| 2017-04 | 2303 | 151 | 93.44 |
| 2017-05 | 3545 | 106 | 97.01 |
| 2017-06 | 3135 | 95 | 96.97 |
| 2017-07 | 3872 | 108 | 97.21 |
| 2017-08 | 4193 | 122 | 97.09 |
| 2017-09 | 4150 | 182 | 95.61 |
| 2017-10 | 4478 | 187 | 95.82 |
| 2017-11 | 7288 | 904 | 87.60 |
| 2017-12 | 5513 | 411 | 92.54 |
| 2018-01 | 7069 | 403 | 94.30 |
| 2018-02 | 6555 | 926 | 85.87 |
| 2018-03 | 7003 | 1328 | 81.04 |
| 2018-04 | 6798 | 306 | 95.50 |
| 2018-05 | 6749 | 443 | 93.44 |
| 2018-06 | 6096 | 71 | 98.84 |
| 2018-07 | 6156 | 208 | 96.62 |
| 2018-08 | 6351 | 393 | 93.81 |

### Q11 — Top 10 sellers by revenue

Review score and late rate are order-level values attributed to each item.

| seller_id | seller_state | orders | items_sold | gmv | avg_review_score | late_delivery_pct |
|---|---|---|---|---|---|---|
| 4869f7a5dfa277a7dca6462dcf3b52b2 | SP | 1131 | 1155 | 229237.63 | 4.13 | 10.54 |
| 53243585a1d6dc2643021fd1853d8905 | BA | 358 | 410 | 222776.05 | 4.08 | 3.00 |
| 4a3ca9315b744ce9f8e9374361493884 | SP | 1804 | 1985 | 200326.12 | 3.80 | 9.70 |
| fa1c13f2614d7b5c4749cbc52fecda94 | SP | 584 | 585 | 192842.13 | 4.34 | 9.15 |
| 7c67e1448b00f6e969d365cea6b010ab | SP | 982 | 1364 | 187923.89 | 3.34 | 8.86 |
| 7e93a43ef30c4f03f38b393420bc753a | SP | 332 | 336 | 172583.88 | 4.24 | 4.66 |
| da8622b14eb17ae2831f4ac5b9dab84a | SP | 1314 | 1551 | 160236.57 | 4.07 | 6.40 |
| 7a67c85e85bb2ce8582c35f2203ad736 | SP | 1159 | 1170 | 141715.54 | 4.24 | 5.19 |
| 1025f0e2d44d7041d6cf58b6550e0bfa | SP | 915 | 1428 | 138968.55 | 3.85 | 6.69 |
| 955fee9216a65b617aa5c0531780ce60 | SP | 1286 | 1498 | 135159.70 | 4.05 | 6.45 |

### Cross-checks between independent outputs

- Q1 totals equal the Gold validation checks: GMV 13,494,400.74, 98,199 revenue orders, 96,470 delivered orders.
- Q5 payment values add up to 15,739,137.01, the payment total in the Gold validation.
- Q7 segment revenue adds up to 13,494,400.74 and its customers to 94,983, equal to Q1.
- Q2 monthly GMV adds up to 13,494,400.74, equal to Q1.
