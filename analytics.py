import warnings
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from oss_utils import OSSClient

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / 'data'
PRICE_DIR = DATA_DIR / 'daily_price'
OUTPUT_DIR = BASE_DIR / 'output'
CONFIG_FILE = BASE_DIR / 'config.json'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_ENCODING = 'utf-8'


def load_categories(path):
    df = pd.read_csv(path, encoding=CSV_ENCODING)
    parent_map = {}
    for _, r in df.iterrows():
        if pd.notna(r['parent']):
            parent_map[r['category_id']] = r['parent']

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
    return df, cat_to_top, top_names


def load_products(path):
    """weight = 鍩烘湡鏁伴噺 q岬⑩個 (Laspeyres 鍏紡)"""
    df = pd.read_csv(path, encoding=CSV_ENCODING)
    base = df[['product_id', 'category_id', 'price', 'weight']].copy()
    base.rename(columns={'price': 'base_price', 'weight': 'base_qty'}, inplace=True)
    return base


def compute_laspeyres_for_day(daily_path, product_base):
    """L = (危 p岬⑩倻路q岬⑩個) / (危 p岬⑩個路q岬⑩個) 脳 100"""
    daily = pd.read_csv(daily_path, encoding=CSV_ENCODING)
    slim = daily[['product_id', 'price']].rename(columns={'price': 'curr_price'})
    m = slim.merge(product_base[['product_id', 'base_price', 'base_qty']],
                   on='product_id', how='inner')
    if m.empty:
        return None
    num = (m['curr_price'] * m['base_qty']).sum()
    den = (m['base_price'] * m['base_qty']).sum()
    if den <= 0:
        return None
    return round((num / den) * 100, 4)


def compute_category_indices(daily_path, product_base, cat_to_top, top_names):
    daily = pd.read_csv(daily_path, encoding=CSV_ENCODING)
    slim = daily[['product_id', 'category_id', 'price']].rename(
        columns={'price': 'curr_price'})
    slim['top_cat_id'] = slim['category_id'].map(cat_to_top)
    m = slim.merge(product_base[['product_id', 'base_price', 'base_qty']],
                   on='product_id', how='inner')
    if m.empty:
        return {}
    indices = {}
    for tid, tname in top_names.items():
        sub = m[m['top_cat_id'] == tid]
        if sub.empty:
            continue
        num = (sub['curr_price'] * sub['base_qty']).sum()
        den = (sub['base_price'] * sub['base_qty']).sum()
        if den > 0:
            indices[tname] = round((num / den) * 100, 4)
    return indices


def plot_main_index(df, save_path):
    fig, ax = plt.subplots(figsize=(16, 7))
    ax.plot(df['date'], df['index'], lw=1.8, color='#2563eb', label='鎷夊紡浠锋牸鎸囨暟')
    ax.axhline(y=100, color='#dc2626', ls='--', lw=1, alpha=0.6, label='鍩烘湡 = 100')

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

    ax.set_title('鎷夊紡浠锋牸鎸囨暟瓒嬪娍鍥?(Laspeyres Price Index)', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('鏃ユ湡', fontsize=11)
    ax.set_ylabel('浠锋牸鎸囨暟 (鍩烘湡 = 100)', fontsize=11)
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
    ax.set_title('鍚勫ぇ绫绘媺寮忎环鏍兼寚鏁板姣?, fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('鏃ユ湡', fontsize=11)
    ax.set_ylabel('浠锋牸鎸囨暟 (鍩烘湡 = 100)', fontsize=11)
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
    print('澶ф暟鎹璁?鈥?鎷夊紡浠锋牸鎸囨暟 (Laspeyres Price Index)')
    print('=' * 60)

    print('\n[1/6] 璇诲彇鍒嗙被鏁版嵁...')
    cat_all, cat_to_top, top_names = load_categories(DATA_DIR / 'categories.csv')
    print(f'  -> {len(cat_all)} 涓垎绫? {len(top_names)} 涓ぇ绫?)

    print('\n[2/6] 璇诲彇鍟嗗搧鍩烘湡鏁版嵁...')
    product_base = load_products(DATA_DIR / 'products.csv')
    print(f'  -> {len(product_base)} 绉嶅晢鍝? 鍩烘湡鏁伴噺鍚堣 {product_base["base_qty"].sum():.2f}')

    print('\n[3/6] 鎵弿姣忔棩浠锋牸鏂囦欢...')
    daily_files = sorted(PRICE_DIR.glob('daily_prices_*.csv'))
    print(f'  -> {len(daily_files)} 涓枃浠?)
    print(f'  -> {daily_files[0].stem[-8:]} ~ {daily_files[-1].stem[-8:]}')

    print('\n[4/6] 閫愭棩璁＄畻鎷夊紡浠锋牸鎸囨暟...')
    results = []
    cat_results = []
    step = max(len(daily_files) // 10, 1)
    for i, f in enumerate(daily_files):
        ds = f.stem.replace('daily_prices_', '')
        dt = datetime.strptime(ds, '%Y%m%d')

        v = compute_laspeyres_for_day(f, product_base)
        if v is not None:
            results.append({'date': dt, 'index': v})

        if i % 30 == 0:
            ci = compute_category_indices(f, product_base, cat_to_top, top_names)
            if ci:
                ci['date'] = dt
                cat_results.append(ci)

        if (i + 1) % step == 0:
            print(f'  -> {(i+1)/len(daily_files)*100:.0f}%')
    print(f'  -> 瀹屾垚! {len(results)} 澶?)

    print('\n[5/6] 鐢熸垚鏇茬嚎鍥?..')
    df_idx = pd.DataFrame(results).sort_values('date').reset_index(drop=True)
    df_idx.to_csv(OUTPUT_DIR / 'laspeyres_index.csv', index=False, encoding='utf-8-sig')
    print(f'  -> 鎸囨暟: {df_idx["index"].min():.2f} ~ {df_idx["index"].max():.2f}')
    plot_main_index(df_idx, OUTPUT_DIR / 'laspeyres_chart.png')
    print(f'  -> 鎬讳綋鏇茬嚎鍥? output/laspeyres_chart.png')

    if cat_results:
        df_cat = pd.DataFrame(cat_results).sort_values('date').reset_index(drop=True)
        df_cat.to_csv(OUTPUT_DIR / 'category_indices.csv', index=False, encoding='utf-8-sig')
        plot_category_indices(df_cat, OUTPUT_DIR / 'category_indices_chart.png')
        print(f'  -> 鍒嗙被鏇茬嚎鍥? output/category_indices_chart.png')

    print('\n[6/6] 涓婁紶鑷抽樋閲屼簯 OSS...')
    oss = OSSClient(CONFIG_FILE)
    if oss.is_configured():
        oss.upload_file(str(DATA_DIR / 'categories.csv'), 'data/categories.csv')
        oss.upload_file(str(DATA_DIR / 'products.csv'), 'data/products.csv')
        oss.upload_file(str(OUTPUT_DIR / 'laspeyres_index.csv'), 'output/laspeyres_index.csv')
        oss.upload_file(str(OUTPUT_DIR / 'laspeyres_chart.png'), 'output/laspeyres_chart.png')
        if cat_results:
            oss.upload_file(str(OUTPUT_DIR / 'category_indices.csv'), 'output/category_indices.csv')
            oss.upload_file(str(OUTPUT_DIR / 'category_indices_chart.png'), 'output/category_indices_chart.png')
        oss.upload_file(str(daily_files[0]), f'data/daily_price/{daily_files[0].name}')
        oss.upload_file(str(daily_files[-1]), f'data/daily_price/{daily_files[-1].name}')
        print(f'  -> 鍏ㄩ儴涓婁紶瀹屾垚! Bucket: {oss.get_bucket_name()}')
    else:
        print('  -> 璺宠繃 (config.json 鏈厤缃?OSS)')
        print('  -> 缂栬緫 config.json 鍚庨噸鏂拌繍琛屽嵆鍙笂浼?)

    print()
    print('=' * 60)
    print('鍏ㄩ儴瀹屾垚!')
    print(f'  鎸囨暟鏁版嵁:   output/laspeyres_index.csv')
    print(f'  鎬讳綋鏇茬嚎鍥? output/laspeyres_chart.png')
    if cat_results:
        print(f'  鍒嗙被鏇茬嚎鍥? output/category_indices_chart.png')
    print('=' * 60)


if __name__ == '__main__':
    main()
