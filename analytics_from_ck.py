# -*- coding: utf-8 -*-
"""
analytics_from_ck.py  — Calculate Laspeyres Price Index from ClickHouse
"""
import sys, warnings, io
from pathlib import Path
BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from ck_utils import ClickHouseClient

warnings.filterwarnings('ignore')

CONFIG = BASE / 'config.json'
OUTPUT_DIR = BASE / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def execute_sql(ck, sql, desc=''):
    print(f'  {desc}...')
    ok, data = ck.execute(sql, timeout=300)
    if not ok:
        print(f'  FAIL: {data}')
        return None
    lines = data.strip().split('\n')
    if len(lines) < 2:
        return pd.DataFrame()
    cols = lines[0].split('\t')
    rows = []
    for line in lines[1:]:
        if line.strip():
            rows.append(line.split('\t'))
    return pd.DataFrame(rows, columns=cols)


def build_category_map(ck):
    sql = 'SELECT category_id, category, hierarchy, parent FROM laspeyres.categories'
    ok, data = ck.execute(sql)
    lines = data.strip().split('\n')
    if len(lines) < 2:
        return {}, {}
    cols = lines[0].split('\t')
    rows = [line.split('\t') for line in lines[1:] if line.strip()]
    df = pd.DataFrame(rows, columns=cols)
    df['category_id'] = df['category_id'].astype(int)
    df['parent'] = pd.to_numeric(df['parent'], errors='coerce')
    df['hierarchy'] = df['hierarchy'].astype(int)
    parent_map = {}
    for _, r in df.iterrows():
        if pd.notna(r['parent']):
            parent_map[r['category_id']] = int(r['parent'])
    def resolve(cid):
        while cid in parent_map:
            cid = parent_map[cid]
        return cid
    cat_to_top = {}
    for _, r in df.iterrows():
        if r['hierarchy'] == 1:
            cat_to_top[r['category_id']] = r['category_id']
        else:
            cat_to_top[r['category_id']] = resolve(r['category_id'])
    top_names = dict(zip(
        df[df['hierarchy'] == 1]['category_id'],
        df[df['hierarchy'] == 1]['category']
    ))
    return cat_to_top, top_names


def plot_main_index(df, save_path):
    fig, ax = plt.subplots(figsize=(16, 7))
    ax.plot(df['date'], df['index'], lw=1.8, color='#2563eb', label='Laspeyres Index')
    ax.axhline(y=100, color='#dc2626', ls='--', lw=1, alpha=0.6, label='Base = 100')
    min_r = df.loc[df['index'].idxmin()]
    max_r = df.loc[df['index'].idxmax()]
    for pt, off, c in [(min_r, (15, -35), '#16a34a'), (max_r, (-15, 20), '#dc2626')]:
        ax.annotate(
            f'{pt["index"]:.2f}\n({pt["date"].strftime("%Y-%m-%d")})',
            (pt['date'], pt['index']),
            xytext=off, textcoords='offset points',
            arrowprops=dict(arrowstyle='->', color='gray', lw=0.8),
            fontsize=9, color=c, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='none', alpha=0.8))
    ax.set_title('Laspeyres Price Index Trend', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Price Index (Base = 100)', fontsize=11)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=10, loc='upper left')
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def plot_category_indices(df_cat, save_path):
    colors = ['#2563eb', '#dc2626', '#16a34a', '#f59e0b',
              '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
    fig, ax = plt.subplots(figsize=(16, 7))
    for idx, col in enumerate(df_cat.columns):
        if col == 'date':
            continue
        ax.plot(df_cat['date'], df_cat[col], lw=1.2,
                color=colors[idx % 8], label=col, alpha=0.85)
    ax.axhline(y=100, color='gray', ls='--', lw=0.8, alpha=0.4)
    ax.set_title('Category Laspeyres Index Comparison', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Price Index (Base = 100)', fontsize=11)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, ncol=2, loc='upper left')
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def main():
    print('=' * 60)
    print('Laspeyres Price Index (ClickHouse Edition)')
    print('=' * 60)

    print('\n[1/5] Connecting to ClickHouse...')
    ck = ClickHouseClient(CONFIG)
    ok, msg = ck.test_connection()
    print(f'  {msg}')
    if not ok:
        print('  Connection failed.'); return

    print('\n[2/5] Loading category mapping...')
    cat_to_top, top_names = build_category_map(ck)
    print(f'  {len(top_names)} top-level categories')

    # Overall index
    print('\n[3/5] Computing overall Laspeyres index in ClickHouse...')
    sql = """
        SELECT d.change_date AS date,
               round(sum(d.price * p.weight) / sum(p.price * p.weight) * 100, 4) AS index_val
        FROM laspeyres.daily_prices d
        JOIN laspeyres.products p ON d.product_id = p.product_id
        GROUP BY d.change_date
        ORDER BY d.change_date
    """
    df_idx = execute_sql(ck, sql, '  SQL (overall index)')
    if df_idx is None or df_idx.empty:
        print('  FAILED'); return
    df_idx['date'] = pd.to_datetime(df_idx['date'])
    df_idx['index'] = df_idx['index_val'].astype(float)

    # Category indices
    print('\n[4/5] Computing category indices in ClickHouse...')
    sql_cat = """
        SELECT d.change_date AS date, d.category_id,
               round(sum(d.price * p.weight) / sum(p.price * p.weight) * 100, 4) AS index_val
        FROM laspeyres.daily_prices d
        JOIN laspeyres.products p ON d.product_id = p.product_id
        GROUP BY d.change_date, d.category_id
        ORDER BY d.change_date, d.category_id
    """
    df_cat_raw = execute_sql(ck, sql_cat, '  SQL (category indices)')

    cat_results = []
    if df_cat_raw is not None and not df_cat_raw.empty:
        df_cat_raw['date'] = pd.to_datetime(df_cat_raw['date'])
        df_cat_raw['category_id'] = df_cat_raw['category_id'].astype(int)
        df_cat_raw['index_val'] = df_cat_raw['index_val'].astype(float)
        df_cat_raw['top_cat_id'] = df_cat_raw['category_id'].map(cat_to_top)
        for tid, tname in top_names.items():
            sub = df_cat_raw[df_cat_raw['top_cat_id'] == tid]
            daily_avg = sub.groupby('date')['index_val'].mean().reset_index()
            daily_avg.columns = ['date', 'index_val']
            for _, row in daily_avg.iterrows():
                cat_results.append({
                    'date': row['date'],
                    'category': tname,
                    'index': row['index_val']
                })

    # Generate charts
    print('\n[5/5] Generating charts...')
    df_idx[['date', 'index']].to_csv(OUTPUT_DIR / 'laspeyres_index.csv', index=False, encoding='utf-8-sig')
    plot_main_index(df_idx, OUTPUT_DIR / 'laspeyres_chart.png')
    print(f'  Overall chart: output/laspeyres_chart.png')
    print(f'  Index range: {df_idx["index"].min():.2f} ~ {df_idx["index"].max():.2f}')

    if cat_results:
        df_cat = pd.DataFrame(cat_results)
        df_pivot = df_cat.pivot_table(
            index='date', columns='category', values='index', aggfunc='mean'
        ).reset_index().sort_values('date')
        df_pivot.to_csv(OUTPUT_DIR / 'category_indices.csv', index=False, encoding='utf-8-sig')
        plot_category_indices(df_pivot, OUTPUT_DIR / 'category_indices_chart.png')
        print(f'  Category chart: output/category_indices_chart.png')

    print()
    print('=' * 60)
    print('Done!')
    print(f'  Index data: output/laspeyres_index.csv')
    print(f'  Overall chart: output/laspeyres_chart.png')
    if cat_results:
        print(f'  Category chart: output/category_indices_chart.png')
    print('=' * 60)


if __name__ == '__main__':
    main()
