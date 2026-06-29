-- ============================================================
-- ClickHouse 正式表建表 & 数据导入（最终版）
-- 课程：大数据应用项目实践
-- 项目：拉式价格指数 (Laspeyres Price Index)
-- 作者：张雨杰  学号：2023337621308
-- 日期：2026年6月
-- 注意：OSS S3 必须用内网域名（-internal），否则超时
-- ============================================================

-- ===== 1. 创建数据库 =====
CREATE DATABASE IF NOT EXISTS laspeyres;


-- ===== 2. 创建 categories 表（272条分类数据） =====
CREATE TABLE IF NOT EXISTS laspeyres.categories (
    category    String,              -- 分类名称
    category_id UInt64,              -- 分类编码（主键）
    hierarchy   UInt8,               -- 层级（1=一级大类，2=二级，3=三级）
    weight      Nullable(Float64),   -- 基期权重比重
    price       Nullable(Float64),   -- 基期价格
    parent      Nullable(Float64)    -- 父分类ID
) ENGINE = MergeTree() ORDER BY category_id;


-- ===== 3. 创建 products 表（70000种商品） =====
CREATE TABLE IF NOT EXISTS laspeyres.products (
    product_id   UInt64,             -- 商品ID（主键）
    category_id  UInt64,             -- 所属分类ID
    name         String,             -- 商品名称
    weight       Float64,            -- 基期数量（权重 q）
    price        Float64,            -- 基期价格 p
    change_count Int32               -- 价格变更次数
) ENGINE = MergeTree() ORDER BY (category_id, product_id);


-- ===== 4. 创建 daily_prices 表（1095天 × ~27000行/天 = 2956万行） =====
CREATE TABLE IF NOT EXISTS laspeyres.daily_prices (
    product_id   UInt64,             -- 商品ID
    category_id  UInt64,             -- 所属分类ID
    name         String,             -- 商品名称
    price        Float64,            -- 当日价格
    change_date  Date                -- 日期
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(change_date)
ORDER BY (change_date, category_id, product_id);


-- ===== 5. 导入 categories（注意：内网域名 + 文件是 UTF-8 编码版本） =====
INSERT INTO laspeyres.categories
SELECT category, category_id, hierarchy, weight, price, parent
FROM s3(
    'http://bigdata-laspeyres-2023337621308.oss-cn-hangzhou-internal.aliyuncs.com/data/categories_utf8.csv',
    'YOUR_ACCESS_KEY_ID',
    'YOUR_ACCESS_KEY_SECRET',
    'CSVWithNames'
);


-- ===== 6. 导入 products =====
INSERT INTO laspeyres.products
SELECT product_id, category_id, name, weight, price, change_count
FROM s3(
    'http://bigdata-laspeyres-2023337621308.oss-cn-hangzhou-internal.aliyuncs.com/data/products.csv',
    'YOUR_ACCESS_KEY_ID',
    'YOUR_ACCESS_KEY_SECRET',
    'CSVWithNames'
);


-- ===== 7. 导入 daily_prices =====
INSERT INTO laspeyres.daily_prices
SELECT product_id, category_id, name, price, change_date
FROM s3(
    'http://bigdata-laspeyres-2023337621308.oss-cn-hangzhou-internal.aliyuncs.com/data/daily_price/daily_prices_*.csv',
    'YOUR_ACCESS_KEY_ID',
    'YOUR_ACCESS_KEY_SECRET',
    'CSVWithNames'
);


-- ===== 8. 导入验证 =====
SELECT 'categories' as table_name, count() as rows FROM laspeyres.categories
UNION ALL
SELECT 'products', count() FROM laspeyres.products
UNION ALL
SELECT 'daily_prices', count() FROM laspeyres.daily_prices;


-- ===== 9. 日期范围验证 =====
SELECT min(change_date), max(change_date), count(DISTINCT change_date)
FROM laspeyres.daily_prices;


-- ===== 10. 在 ClickHouse 中计算拉式价格指数（可直接替代 analytics.py） =====
SELECT
    d.change_date,
    round(sum(d.price * p.weight) / sum(p.price * p.weight) * 100, 4) AS laspeyres_index
FROM laspeyres.daily_prices d
JOIN laspeyres.products p ON d.product_id = p.product_id
GROUP BY d.change_date
ORDER BY d.change_date;
