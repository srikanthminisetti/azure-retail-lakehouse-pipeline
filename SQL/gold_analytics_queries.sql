/* =====================================================================================
   Conventions
   - Revenue orders exclude canceled and unavailable orders; GMV = sum of item price (freight separate).
   - Boolean Gold columns appear as bit in the endpoint, so filters use = 1 / = 0.
   - String comparisons are case-sensitive in the endpoint; the source values are lower case.
   - Late = delivered on a date after the estimated delivery date; delivery_delay_days > 0.
   ===================================================================================== */


-- Q0  Sanity check: Gold row counts against the values reported by notebook 03
-- Business question: is every Gold table present and complete?
SELECT 'gold_dim_date' AS table_name, COUNT(*) AS row_count, 774 AS expected_rows FROM dbo.gold_dim_date
UNION ALL SELECT 'gold_dim_customer', COUNT(*), 96096 FROM dbo.gold_dim_customer
UNION ALL SELECT 'gold_dim_product', COUNT(*), 32951 FROM dbo.gold_dim_product
UNION ALL SELECT 'gold_dim_seller', COUNT(*), 3095 FROM dbo.gold_dim_seller
UNION ALL SELECT 'gold_fact_orders', COUNT(*), 99441 FROM dbo.gold_fact_orders
UNION ALL SELECT 'gold_fact_order_items', COUNT(*), 112650 FROM dbo.gold_fact_order_items
UNION ALL SELECT 'gold_daily_sales', COUNT(*), 614 FROM dbo.gold_daily_sales
UNION ALL SELECT 'gold_payment_method_performance', COUNT(*), 4 FROM dbo.gold_payment_method_performance
UNION ALL SELECT 'gold_product_category_sales', COUNT(*), 74 FROM dbo.gold_product_category_sales
UNION ALL SELECT 'gold_customer_summary', COUNT(*), 94983 FROM dbo.gold_customer_summary
UNION ALL SELECT 'gold_delivery_performance', COUNT(*), 556 FROM dbo.gold_delivery_performance;


-- Q1  Headline KPIs
-- Business question: how big is the business and how well does it deliver?
-- Sources: gold_daily_sales (sales), gold_customer_summary (customers), gold_fact_orders (delivery).
SELECT
    (SELECT CAST(SUM(gmv) AS DECIMAL(18,2)) FROM dbo.gold_daily_sales)                          AS total_gmv,
    (SELECT CAST(SUM(freight) AS DECIMAL(18,2)) FROM dbo.gold_daily_sales)                      AS total_freight,
    (SELECT SUM(orders) FROM dbo.gold_daily_sales)                                              AS revenue_orders,
    (SELECT COUNT(*) FROM dbo.gold_customer_summary)                                            AS customers,
    (SELECT CAST(SUM(gmv) * 1.0 / SUM(orders) AS DECIMAL(10,2)) FROM dbo.gold_daily_sales)      AS avg_order_value,
    (SELECT COUNT(*) FROM dbo.gold_fact_orders WHERE is_delivered = 1)                          AS delivered_orders,
    (SELECT CAST(100.0 * SUM(CASE WHEN is_late = 1 THEN 0 ELSE 1 END) / COUNT(*) AS DECIMAL(5,2))
       FROM dbo.gold_fact_orders WHERE is_delivered = 1)                                        AS on_time_pct;


-- Q2  Monthly sales trend with month-over-month growth
-- Business question: how are sales trending?
-- Growth is shown only when BOTH months have at least 100 orders. The first (2016) and last (2018-09/10) months are
-- tiny partial months in this dataset, and comparing them with full months would give meaningless percentages.
WITH monthly AS (
    SELECT d.year_month,
           SUM(s.orders)                          AS orders,
           CAST(SUM(s.gmv) AS DECIMAL(18,2))      AS gmv,
           CAST(SUM(s.freight) AS DECIMAL(18,2))  AS freight
    FROM dbo.gold_daily_sales AS s
    JOIN dbo.gold_dim_date    AS d ON d.date_key = s.date_key
    GROUP BY d.year_month
),
with_previous AS (
    SELECT year_month, orders, gmv, freight,
           LAG(gmv)    OVER (ORDER BY year_month) AS prev_gmv,
           LAG(orders) OVER (ORDER BY year_month) AS prev_orders
    FROM monthly
)
SELECT year_month,
       orders,
       gmv,
       freight,
       CAST(gmv * 1.0 / orders AS DECIMAL(10,2)) AS avg_order_value,
       CASE WHEN orders >= 100 AND prev_orders >= 100
            THEN CAST(100.0 * (gmv - prev_gmv) / prev_gmv AS DECIMAL(10,1)) END AS gmv_mom_pct
FROM with_previous
ORDER BY year_month;


-- Q3  Top 10 product categories by revenue
-- Business question: which categories earn the most?
-- Review score and late rate are item-weighted averages of order-level values.
SELECT TOP 10
       RANK() OVER (ORDER BY revenue DESC)                          AS revenue_rank,
       category,
       units_sold,
       orders,
       CAST(revenue AS DECIMAL(18,2))                               AS revenue,
       CAST(100.0 * revenue / SUM(revenue) OVER () AS DECIMAL(5,2)) AS revenue_share_pct,
       avg_price,
       avg_review_score,
       CAST(100.0 * late_delivery_rate AS DECIMAL(5,2))             AS late_delivery_pct
FROM dbo.gold_product_category_sales
ORDER BY revenue DESC;


-- Q4  Revenue concentration (Pareto): the categories that together make up the first 80% of revenue
-- Business question: how concentrated is revenue?
WITH shares AS (
    SELECT category,
           CAST(revenue AS DECIMAL(18,2)) AS revenue,
           100.0 * revenue / SUM(revenue) OVER () AS own_pct
    FROM dbo.gold_product_category_sales
),
cumulative AS (
    SELECT category, revenue, own_pct,
           ROW_NUMBER() OVER (ORDER BY revenue DESC, category) AS category_rank,
           SUM(own_pct) OVER (ORDER BY revenue DESC, category
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_pct
    FROM shares
)
SELECT category_rank,
       category,
       revenue,
       CAST(own_pct AS DECIMAL(5,2))        AS revenue_share_pct,
       CAST(cumulative_pct AS DECIMAL(5,2)) AS cumulative_share_pct
FROM cumulative
WHERE cumulative_pct - own_pct < 80          -- rows that are still needed to reach 80%
ORDER BY category_rank;


-- Q5  Payment method mix
-- Business question: how do customers pay?
-- Grain: payment type; revenue orders only. An order with split payments counts once per payment type it uses.
SELECT payment_type,
       orders,
       payment_rows,
       CAST(payment_value AS DECIMAL(18,2))          AS payment_value,
       CAST(100.0 * share_of_payment_value AS DECIMAL(5,2)) AS share_of_value_pct,
       avg_installments,
       avg_payment_value
FROM dbo.gold_payment_method_performance
ORDER BY payment_value DESC;


-- Q6  Repeat-customer rate
-- Business question: how many customers come back, and how much revenue do they bring?
-- Customers are real people (customer_unique_id), not the per-order customer_id.
SELECT COUNT(*)                                                                      AS customers,
       SUM(CASE WHEN is_repeat_customer = 1 THEN 1 ELSE 0 END)                       AS repeat_customers,
       CAST(100.0 * SUM(CASE WHEN is_repeat_customer = 1 THEN 1 ELSE 0 END)
            / COUNT(*) AS DECIMAL(5,2))                                              AS repeat_customer_pct,
       CAST(100.0 * SUM(CASE WHEN is_repeat_customer = 1 THEN total_spent ELSE 0 END)
            / SUM(total_spent) AS DECIMAL(5,2))                                      AS repeat_revenue_pct,
       CAST(AVG(total_spent) AS DECIMAL(10,2))                                       AS avg_spent_per_customer
FROM dbo.gold_customer_summary;


-- Q7  Customer recency segments
-- Business question: how recently did customers last buy, and how much are they worth?
-- Recency is measured from the last order date in the data (not from today), because the dataset is historical.
SELECT recency_segment,
       COUNT(*)                                                    AS customers,
       CAST(SUM(total_spent) AS DECIMAL(18,2))                     AS revenue,
       CAST(AVG(total_spent) AS DECIMAL(10,2))                     AS avg_spent,
       SUM(CASE WHEN is_repeat_customer = 1 THEN 1 ELSE 0 END)     AS repeat_customers
FROM (
    SELECT total_spent, is_repeat_customer,
           CASE WHEN recency_days <= 90  THEN '1. 0-90 days'
                WHEN recency_days <= 180 THEN '2. 91-180 days'
                WHEN recency_days <= 365 THEN '3. 181-365 days'
                ELSE                          '4. over 365 days' END AS recency_segment
    FROM dbo.gold_customer_summary
) AS c
GROUP BY recency_segment
ORDER BY recency_segment;


-- Q8  Late delivery by customer state (10 weakest states with at least 500 delivered orders)
-- Business question: where is delivery performance weakest?
-- Uses the order-grain fact so the averages are exact.
SELECT TOP 10
       customer_state                                                          AS state,
       COUNT(*)                                                                AS delivered_orders,
       CAST(AVG(delivery_days * 1.0) AS DECIMAL(6,2))                          AS avg_delivery_days,
       SUM(CASE WHEN is_late = 1 THEN 1 ELSE 0 END)                            AS late_orders,
       CAST(100.0 * SUM(CASE WHEN is_late = 1 THEN 0 ELSE 1 END) / COUNT(*) AS DECIMAL(5,2)) AS on_time_pct
FROM dbo.gold_fact_orders
WHERE is_delivered = 1
GROUP BY customer_state
HAVING COUNT(*) >= 500
ORDER BY on_time_pct ASC, customer_state;


-- Q9  Does late delivery hurt review scores?
-- Business question: how much does the delivery delay change customer satisfaction?
-- delivery_delay_days = delivered date - estimated date (negative = early). Review score = latest review of the order.
SELECT delay_bucket,
       COUNT(*)                                                              AS reviewed_orders,
       CAST(AVG(review_score * 1.0) AS DECIMAL(4,2))                         AS avg_review_score,
       CAST(100.0 * SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,2)) AS low_score_pct
FROM (
    SELECT review_score,
           CASE WHEN delivery_delay_days <= -8 THEN '1. 8+ days early'
                WHEN delivery_delay_days <= -1 THEN '2. 1-7 days early'
                WHEN delivery_delay_days = 0   THEN '3. on the estimated date'
                WHEN delivery_delay_days <= 3  THEN '4. 1-3 days late'
                WHEN delivery_delay_days <= 7  THEN '5. 4-7 days late'
                ELSE                                '6. 8+ days late' END AS delay_bucket
    FROM dbo.gold_fact_orders
    WHERE is_delivered = 1 AND review_score IS NOT NULL
) AS o
GROUP BY delay_bucket
ORDER BY delay_bucket;


-- Q10  Monthly on-time delivery trend
-- Business question: has delivery performance improved or deteriorated over time?
-- Built from the delivery mart; sums of counts, so the rate is exact. Tiny months (under 100 delivered orders) are excluded.
SELECT order_month,
       SUM(delivered_orders) AS delivered_orders,
       SUM(late_orders)      AS late_orders,
       CAST(100.0 * (1 - SUM(late_orders) * 1.0 / SUM(delivered_orders)) AS DECIMAL(5,2)) AS on_time_pct
FROM dbo.gold_delivery_performance
GROUP BY order_month
HAVING SUM(delivered_orders) >= 100          -- months with fewer than 100 delivered orders are too small to judge
ORDER BY order_month;


-- Q11  Top 10 sellers by revenue
-- Business question: which sellers matter most, and how good is their service?
-- Fact-to-dimension join (item grain -> seller). Review score and late rate are order-level values per item.
SELECT TOP 10
       s.seller_id,
       d.state                                                                  AS seller_state,
       COUNT(DISTINCT s.order_id)                                               AS orders,
       COUNT(*)                                                                 AS items_sold,
       CAST(SUM(s.price) AS DECIMAL(18,2))                                      AS gmv,
       CAST(AVG(s.review_score * 1.0) AS DECIMAL(4,2))                          AS avg_review_score,
       CAST(100.0 * AVG(CASE WHEN s.is_delivered = 1
                             THEN CASE WHEN s.is_late = 1 THEN 1.0 ELSE 0.0 END END) AS DECIMAL(5,2)) AS late_delivery_pct
FROM dbo.gold_fact_order_items AS s
JOIN dbo.gold_dim_seller       AS d ON d.seller_id = s.seller_id
WHERE s.is_revenue_order = 1
GROUP BY s.seller_id, d.state
ORDER BY gmv DESC;
