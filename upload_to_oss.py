# -*- coding: utf-8 -*-
"""
upload_to_oss.py — 将本地数据上传到阿里云 OSS
配置从 config.json 读取，请先编辑 config.json
"""
import os, json, sys
import oss2
from pathlib import Path

# 从 config.json 读取配置
config_path = Path(__file__).parent / 'config.json'
if not config_path.exists():
    print('Error: config.json not found. Please create it first.')
    sys.exit(1)

with open(config_path, encoding='utf-8') as f:
    cfg = json.load(f)['oss']

ACCESS_KEY_ID = cfg['access_key_id']
ACCESS_KEY_SECRET = cfg['access_key_secret']
ENDPOINT = cfg['endpoint']
BUCKET_NAME = cfg['bucket_name']

DATA_DIR = Path(__file__).parent / 'data'

FILE_MAP = [
    (str(DATA_DIR / 'categories.csv'), 'data/categories.csv'),
    (str(DATA_DIR / 'products.csv'), 'data/products.csv'),
]

def progress_callback(bytes_consumed, total_bytes):
    if total_bytes > 0:
        pct = bytes_consumed * 100 / total_bytes
        print(f'\r  upload: {bytes_consumed}/{total_bytes} bytes ({pct:.1f}%)', end='')

def upload_file(bucket, local_path, oss_key):
    if not os.path.isfile(local_path):
        print(f'  [SKIP] File not found: {local_path}')
        return
    file_size = os.path.getsize(local_path)
    print(f'  upload: {oss_key} ({file_size/1024:.1f} KB)')
    try:
        with open(local_path, 'rb') as f:
            bucket.put_object(oss_key, f, progress_callback=progress_callback)
        print(f'\n  OK: {oss_key}')
    except Exception as e:
        print(f'\n  FAIL: {oss_key} — {e}')

def main():
    auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)
    try:
        bucket.get_bucket_info()
        print(f'Connected to OSS Bucket: {BUCKET_NAME}\n')
    except Exception as e:
        print(f'Connection failed: {e}')
        return

    print('=== Upload main files ===')
    for local_path, oss_key in FILE_MAP:
        upload_file(bucket, local_path, oss_key)

    print('\n=== Upload daily_price files ===')
    daily_price_dir = DATA_DIR / 'daily_price'
    if not daily_price_dir.is_dir():
        print(f'  [SKIP] Directory not found: {daily_price_dir}')
        return
    csv_files = sorted([f for f in os.listdir(daily_price_dir) if f.endswith('.csv')])
    total = len(csv_files)
    print(f'  Found {total} daily_price CSV files')
    for idx, filename in enumerate(csv_files, 1):
        local_path = daily_price_dir / filename
        oss_key = f'data/daily_price/{filename}'
        file_size = os.path.getsize(local_path)
        print(f'  [{idx}/{total}] {filename} ({file_size/1024:.1f} KB)')
        try:
            with open(local_path, 'rb') as f:
                bucket.put_object(oss_key, f)
            print(f'    OK')
        except Exception as e:
            print(f'    FAIL: {e}')
    print('\nDone!')

if __name__ == '__main__':
    main()
