# -*- coding: utf-8 -*-
"""
connector.py — 数据上传：全部通过 ClickHouse S3 引擎，不经过 Python
"""
import sys, argparse
from pathlib import Path
BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))
from ck_utils import ClickHouseClient
from oss_utils import OSSClient

CONFIG = BASE / 'config.json'
BUCKET = 'bigdata-laspeyres-2023337621308'
ENDPOINT = 'oss-cn-hangzhou-internal.aliyuncs.com'

def s3_url(path):
    return f'http://{BUCKET}.{ENDPOINT}/{path}'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-test', action='store_true')
    parser.add_argument('--with-prices', action='store_true')
    args = parser.parse_args()

    print('=' * 60)
    print('Connector — S3 Engine')
    print('=' * 60)

    oss = OSSClient(CONFIG)
    if not oss.is_configured(): print('OSS not configured'); return
    cfg = oss._load_config()
    AK, SK = cfg['access_key_id'], cfg['access_key_secret']

    print('\n[1/3] Connecting to ClickHouse...')
    ck = ClickHouseClient(CONFIG)
    ok, msg = ck.test_connection()
    print(f'  {msg}')
    if not ok: return

    print('\n[2/3] Creating tables...')
    ck.create_tables()

    print('\n[3/3] Importing via S3 engine...')

    # categories — 用 UTF-8 版本
    sql = f"""INSERT INTO categories
        SELECT category, category_id, hierarchy, weight, price, parent
        FROM s3('{s3_url('data/categories_utf8.csv')}', '{AK}', '{SK}', 'CSVWithNames')"""
    ok, msg = ck.execute(sql, timeout=30)
    print(f'  categories: {"OK" if ok else "FAIL"}')
    if not ok: print(f'    {msg}')

    # products — 直接读（中文名乱码不影响数值计算）
    sql = f"""INSERT INTO products
        SELECT toUInt64(product_id), toUInt64(category_id), name,
               toFloat64(weight), toFloat64(price), toInt32(change_count)
        FROM s3('{s3_url('data/products.csv')}', '{AK}', '{SK}', 'CSVWithNames')"""
    ok, msg = ck.execute(sql, timeout=30)
    print(f'  products: {"OK" if ok else "FAIL"}')
    if not ok: print(f'    {msg}')

    # daily_prices — 通配符读所有文件
    if args.with_prices:
        sql = f"""INSERT INTO daily_prices
            SELECT toUInt64(product_id), toUInt64(category_id), name,
                   toFloat64(price), toDate(change_date)
            FROM s3('{s3_url('data/daily_price/daily_prices_*.csv')}', '{AK}', '{SK}', 'CSVWithNames')"""
        print('  daily_prices: importing (may take 2-3 minutes)...')
        ok, msg = ck.execute(sql, timeout=600)
        print(f'  daily_prices: {"OK" if ok else "FAIL"}')
        if not ok: print(f'    {msg}')

    print('\n' + '=' * 60)
    print('Done!')
    print('=' * 60)

if __name__ == '__main__':
    main()
