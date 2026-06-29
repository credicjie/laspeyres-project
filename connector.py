# ci-test
import sys, argparse
from pathlib import Path
BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))

from oss_utils import OSSClient
from ck_utils import ClickHouseClient

CONFIG = BASE / 'config.json'

def main():
    parser = argparse.ArgumentParser(description='数据连接器: OSS -> ClickHouse')
    parser.add_argument('--skip-test', action='store_true', help='跳过单元测试')
    parser.add_argument('--with-prices', action='store_true', help='同时上传 daily_prices（耗时较长）')
    args = parser.parse_args()

    print('=' * 60)
    print('大数据课设 - 数据连接器')
    print('=' * 60)

    print('\n[1/5] 初始化 OSS 客户端...')
    oss = OSSClient(CONFIG)
    if not oss.is_configured():
        print('  OSS 未配置'); return
    print(f'  OSS Bucket: {oss.get_bucket_name()}')

    print('\n[2/5] 初始化 ClickHouse 客户端...')
    ck = ClickHouseClient(CONFIG)
    print(f'  CK 目标: {ck.get_info()}')

    if not args.skip_test:
        print('\n[3/5] 运行单元测试...')
        if not ck.test_small_transfer(oss):
            print('  测试失败，请检查后重试'); return
    else:
        print('\n[3/5] 跳过单元测试')

    print('\n[4/5] 创建 ClickHouse 表...')
    ck.create_tables()

    print('\n[5/5] 上传数据...')
    files = [
        ('categories', 'data/categories_utf8.csv'),
        ('products', 'data/products.csv'),
    ]
    for table, oss_key in files:
        raw = oss.read_raw(oss_key)
        if raw is None: print(f'  SKIP: {oss_key}'); continue
        data_lines = '\n'.join(raw.strip().split('\n')[1:])
        if not data_lines.strip(): print(f'  SKIP: {oss_key} 为空'); continue
        ok, msg = ck.insert_csv(table, data_lines)
        print(f'  {table}: {"OK" if ok else "FAIL"}')
        if not ok: print(f'    错误: {msg}')

    # 上传 daily_prices（通过 S3 引擎，数据直传不经过本地）
    if args.with_prices:
        print('\n  -> 上传 daily_prices（这步走 CK 内网 S3 引擎，较快）...')
        c = ck._load()
        sql = f"""
        INSERT INTO daily_prices
        SELECT product_id, category_id, name, price, change_date
        FROM s3(
            'http://{oss.get_bucket_name()}.oss-cn-hangzhou-internal.aliyuncs.com/data/daily_price/daily_prices_*.csv',
            '{oss._load_config()['access_key_id']}',
            '{oss._load_config()['access_key_secret']}',
            'CSVWithNames'
        )"""
        ok, msg = ck.execute(sql, timeout=600)
        print(f'  daily_prices: {"OK" if ok else "FAIL"}')
        if not ok: print(f'    错误: {msg}')

    print('\n' + '=' * 60)
    print('全部完成!')
    print('=' * 60)

if __name__ == '__main__':
    main()
