# -*- coding: utf-8 -*-
"""
test_connector.py  — 单元测试
用途：在执行正式上传前，用小数据验证 OSS -> ClickHouse 链路是否连通
运行：python test_connector.py
说明：编辑 config.json 中的 clickhouse 字段可切换目标实例
"""
import sys
import json
from pathlib import Path

BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))

from oss_utils import OSSClient
from ck_utils import ClickHouseClient

# 定义配置文件路径
CONFIG = BASE / 'config.json'

# --- 调试代码块：读取并打印配置 ---
try:
    with open(CONFIG, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[DEBUG] 读取成功！JSON 中包含的顶级字段: {list(data.keys())}")
    if 'oss' in data:
        print(f"[DEBUG] OSS 配置项包含: {list(data['oss'].keys())}")
    else:
        print("[DEBUG] 警告：JSON 中没有 'oss' 字段！")
except FileNotFoundError:
    print(f"[DEBUG] 致命错误：找不到配置文件 {CONFIG}")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"[DEBUG] 致命错误：config.json 格式有误！错误位置：第 {e.lineno} 行，第 {e.colno} 列")
    sys.exit(1)
except Exception as e:
    print(f"[DEBUG] 读取配置时发生未知错误: {e}")
    sys.exit(1)

# --- 主程序 ---
def main():
    print('=' * 60)
    print('单元测试: OSS -> ClickHouse 连通性验证')
    print('=' * 60)

    oss = OSSClient(CONFIG)
    if not oss.is_configured():
        print('\n[FAIL] OSS 未配置，请检查 config.json')
        return

    ck = ClickHouseClient(CONFIG)

    # 执行小规模传输测试
    result = ck.test_small_transfer(oss)

    print()
    if result:
        print('测试结论: OSS -> ClickHouse 链路正常，可以执行正式上传')
    else:
        print('测试结论: 链路异常，请检查以下项目：')
        print('  1. config.json 中的 ClickHouse 配置')
        print('  2. ClickHouse 集群是否在运行')
        print('  3. 网络是否能访问 ClickHouse 端口')
    print('=' * 60)

if __name__ == '__main__':
    main()