# -*- coding: utf-8 -*-
"""
validate_data.py  — 数据格式校验
用途：在 CI/CD 中执行，检查 CSV 数据格式是否正确
检查项：文件存在性、字段完整性、数值类型、日期格式、分类层级一致性
"""
import sys, os
from pathlib import Path

DATA_DIR = Path(__file__).parent / 'data'
errors = 0

def check(cond, msg):
    global errors
    if not cond:
        print(f'  [FAIL] {msg}')
        errors += 1
    else:
        print(f'  [OK]   {msg}')

print('=' * 60)
print('Data Validation')
print('=' * 60)

# 1. categories.csv
print('\n--- categories.csv ---')
path = DATA_DIR / 'categories.csv'
check(path.exists(), 'File exists')
if path.exists():
    import pandas as pd
    df = pd.read_csv(path, encoding='utf-8')
    check(len(df) == 272, f'Row count: {len(df)} (expect 272)')
    check('category_id' in df.columns, 'Has category_id column')
    check('category' in df.columns, 'Has category column')
    check('hierarchy' in df.columns, 'Has hierarchy column')
    check('parent' in df.columns, 'Has parent column')
    check(df['hierarchy'].isin([1,2,3]).all(), 'Hierarchy values 1/2/3 only')
    check(df['category_id'].is_unique, 'category_id is unique')
    check(df['category'].notna().all(), 'No null category names')

# 2. products.csv
print('\n--- products.csv ---')
path = DATA_DIR / 'products.csv'
check(path.exists(), 'File exists')
if path.exists():
    df = pd.read_csv(path, encoding='utf-8')
    check(len(df) == 70000, f'Row count: {len(df)} (expect 70000)')
    check('product_id' in df.columns, 'Has product_id column')
    check('category_id' in df.columns, 'Has category_id column')
    check('name' in df.columns, 'Has name column')
    check('price' in df.columns, 'Has price column')
    check('weight' in df.columns, 'Has weight column')
    check(df['price'].dtype in ['float64', 'int64'], 'price is numeric')
    check(df['weight'].dtype in ['float64', 'int64'], 'weight is numeric')
    check(df['price'].min() >= 0, 'No negative prices')
    check(df['weight'].min() >= 0, 'No negative weights')

# 3. daily_price files
print('\n--- daily_price/ ---')
price_dir = DATA_DIR / 'daily_price'
files = sorted(price_dir.glob('daily_prices_*.csv'))
check(len(files) > 0, f'Found {len(files)} CSV files')
if files:
    # Check first file
    df = pd.read_csv(files[0], encoding='gbk')
    check('product_id' in df.columns, 'Has product_id column')
    check('price' in df.columns, 'Has price column')
    check('change_date' in df.columns, 'Has change_date column')
    check(df['price'].dtype in ['float64', 'int64'], 'price is numeric')
    # Check date format
    dates = pd.to_datetime(df['change_date'], errors='coerce')
    check(dates.notna().all(), 'All dates are valid')
    # Check naming convention
    name_ok = all(f.name == f'daily_prices_{pd.to_datetime(df.iloc[0]["change_date"]):%Y%m%d}.csv'
                  for f in [files[0]])
    # Just check file name matches date
    fname_date = files[0].stem.replace('daily_prices_', '')
    file_dt = pd.Timestamp(fname_date)
    csv_dt = pd.Timestamp(df['change_date'].iloc[0])
    check(file_dt == csv_dt, 'File name matches internal date')

print(f'\n{"=" * 60}')
if errors == 0:
    print('All checks passed!')
else:
    print(f'{errors} check(s) FAILED')
print(f'{"=" * 60}')
sys.exit(0 if errors == 0 else 1)
