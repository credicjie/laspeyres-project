# -*- coding: utf-8 -*-
"""ClickHouse 工具类"""
import json, io, sys, os
from pathlib import Path

class ClickHouseClient:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self._cfg = None

    def _load(self):
        if self._cfg is not None:
            return self._cfg
        with open(self.config_path, encoding='utf-8') as f:
            self._cfg = json.load(f)['clickhouse']
        return self._cfg

    def get_info(self):
        c = self._load()
        return f"{c['user']}@{c['host']}:{c['port']}/{c['database']}"

    def execute(self, sql, db=None, timeout=60):
        c = self._load()
        import requests
        url = f"http://{c['host']}:{c['port']}/?default_format=TabSeparatedWithNames"
        params = {'database': db or c['database']}
        try:
            r = requests.post(url, params=params, auth=(c['user'], c['password']),
                              data=sql.encode('utf-8'), timeout=timeout)
            if r.status_code == 200:
                return True, r.text.strip()
            return False, f"[{r.status_code}] {r.text[:200]}"
        except Exception as e:
            return False, str(e)

    def test_connection(self):
        ok, res = self.execute('SELECT 1', db='default')
        if ok and '1' in res:
            return True, f"OK: {self.get_info()}"
        return False, f"FAIL: {res}"

    def create_database(self):
        print("  -> 创建数据库 laspeyres...")
        ok, msg = self.execute('CREATE DATABASE IF NOT EXISTS laspeyres', db='default')
        print(f"  laspeyres: {'OK' if ok else 'FAIL'}")
        if not ok: print(f"    错误: {msg}")

    def test_small_transfer(self, oss):
        print("\n===== 单元测试: OSS -> ClickHouse =====")
        ok, msg = self.test_connection()
        print(f"  [1/4] 连接 {self.get_info()}: {'OK' if ok else 'FAIL'}")
        if not ok: print(f"    错误: {msg}"); return False
        print("  [1b/4] 确保数据库存在...")
        self.create_database()
        import pandas as pd
        print("  [2/4] 从 OSS 读取 1 行...")
        csv_bytes = oss.read_raw('data/products.csv')
        if csv_bytes is None: print("  [2/4] FAIL"); return False
        sample = pd.read_csv(io.StringIO(csv_bytes), nrows=1, encoding='gbk')
        print(f"  [2/4] OK")
        print("  [3/4] 写入 ClickHouse...")
        self.execute("DROP TABLE IF EXISTS __test_link")
        ok, _ = self.execute("""CREATE TABLE __test_link (
            product_id UInt64, category_id UInt64, name String,
            weight Float64, price Float64, change_count Int32
        ) ENGINE = Memory()""")
        if not ok: print("  [3/4] FAIL"); self.execute("DROP TABLE IF EXISTS __test_link"); return False
        csv_buf = io.StringIO()
        sample.to_csv(csv_buf, index=False, header=False, encoding='utf-8')
        csv_buf.seek(0)
        c = self._load()
        import requests
        try:
            r = requests.post(f"http://{c['host']}:{c['port']}/",
                params={'database': c['database']},
                auth=(c['user'], c['password']),
                data=("INSERT INTO __test_link FORMAT CSV\n" + csv_buf.getvalue()).encode('utf-8'), timeout=30)
            if r.status_code != 200: print(f"  [3/4] FAIL: {r.text[:100]}"); self.execute("DROP TABLE IF EXISTS __test_link"); return False
        except Exception as e: print(f"  [3/4] FAIL: {e}"); self.execute("DROP TABLE IF EXISTS __test_link"); return False
        ok, data = self.execute("SELECT count(), product_id, name FROM __test_link GROUP BY product_id, name")
        self.execute("DROP TABLE IF EXISTS __test_link")
        if ok and data:
            print(f"  [4/4] 验证 OK")
            print("\n  OSS -> ClickHouse 全链路测试通过!"); return True
        print("  [4/4] FAIL"); return False

    def create_tables(self):
        self.create_database()
        print("  -> 创建数据表...")
        for name, sql in [
            ("categories", """CREATE TABLE IF NOT EXISTS categories (
                category String, category_id UInt64, hierarchy UInt8,
                weight Nullable(Float64), price Nullable(Float64), parent Nullable(Float64)
            ) ENGINE = MergeTree() ORDER BY category_id"""),
            ("products", """CREATE TABLE IF NOT EXISTS products (
                product_id UInt64, category_id UInt64, name String,
                weight Float64, price Float64, change_count Int32
            ) ENGINE = MergeTree() ORDER BY (category_id, product_id)"""),
            ("daily_prices", """CREATE TABLE IF NOT EXISTS daily_prices (
                product_id UInt64, category_id UInt64, name String,
                price Float64, change_date Date
            ) ENGINE = MergeTree() PARTITION BY toYYYYMM(change_date)
            ORDER BY (change_date, category_id, product_id)""")
        ]:
            ok, msg = self.execute(sql)
            print(f"  {name}: {'OK' if ok else 'FAIL'}")
            if not ok: print(f"    错误: {msg}")

    def insert_csv(self, table, csv_content):
        c = self._load()
        import requests
        sql = f"INSERT INTO {table} FORMAT CSV\n"
        try:
            r = requests.post(f"http://{c['host']}:{c['port']}/",
                params={'database': c['database']},
                auth=(c['user'], c['password']),
                data=(sql + csv_content).encode('utf-8'), timeout=300)
            return r.status_code == 200, r.text[:200] if r.status_code != 200 else ''
        except Exception as e:
            return False, str(e)
