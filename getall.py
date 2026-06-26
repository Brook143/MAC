import pandas as pd
from datetime import datetime, timedelta
import tushare as ts
from rediscache import RedisCache
import requests
import os
from dotenv import load_dotenv
load_dotenv()

requests.utils.default_user_agent = lambda: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

cache = RedisCache(password=os.getenv("REDIS_PASSWORD"))
today = datetime.now().strftime("%Y%m%d")
start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
pro = ts.pro_api(os.getenv("TUSHARE_TOKEN"))


def compute_consecutive_up(df_stock):
    """从最新日期开始，计算连续上涨天数"""
    df_sorted = df_stock.sort_values('trade_date', ascending=False)
    cnt = 0
    for _, row in df_sorted.iterrows():
        if row['pct_chg'] > 0:
            cnt += 1
        else:
            break
    return cnt


def fetch_and_cache():
    try:
        print(f"[{datetime.now()}] 开始拉取数据，时间范围：{start_date} 至 {today}")
        
        # 1. 分页拉取数据
        df_list = []
        offset = 0
        page_size = 5000
        while True:
            page = pro.daily(
                start_date=start_date,
                end_date=today,
                limit=page_size,
                offset=offset,
                fields="ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount,change"
            )
            if page is None or page.empty:
                break
            df_list.append(page)
            print(f"  page {offset // page_size + 1}: {len(page)} 条")
            if len(page) < page_size:
                break
            offset += page_size
        df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        
        # 筛选主板
        df = df[df['ts_code'].str.match(r'^((00[0123])|(60[0135]))\d{3}')]
        
        if df.empty:
            print(f"[{datetime.now()}] 未获取到任何数据")
            return
        
        # ✅ 最小必要修复：强制类型转换，防止tushare返回字符串导致比较异常
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce')
        df['trade_date'] = df['trade_date'].astype(str)
        
        # 过滤异常
        df = df.dropna(subset=['pct_chg'])
        

        # 按股票代码和日期降序排序，保留每只股票的最新记录（用于缓存）
        df_latest = df.sort_values(['ts_code', 'trade_date'], ascending=False).drop_duplicates('ts_code')
        
        # 2. 计算连涨天数（使用你的简单版，逐只股票计算）
        print(f"[{datetime.now()}] 开始计算连涨天数...")
        consec_map = {}
        for code, group in df.groupby('ts_code'):
            consec_map[code] = compute_consecutive_up(group)
        
        print(f"[{datetime.now()}] 连涨天数计算完成")
        
        
        # 3. 批量写入Redis（保持你原来的缓存逻辑）
        BATCH_SIZE = 1000
        pipe = cache.pipeline()
        count = 0
        
        for _, row in df_latest.iterrows():
            code = row['ts_code']
            spot_data = {k: str(v) for k, v in row.to_dict().items() 
                        if pd.notna(v) and k != 'latest_date'}
            spot_data['up_days'] = str(consec_map.get(code, 0))
            
            spot_key = f"stock:spot:{code}"
            pipe.hset(spot_key, mapping=spot_data)
            pipe.expire(spot_key, 86400 * 3)
            
            count += 1
            if count % BATCH_SIZE == 0:
                pipe.execute()
                pipe = cache.pipeline()
                print(f"[{datetime.now()}] 已写入 {count} 只股票")
        
        pipe.execute()
        
        codes = df_latest['ts_code'].tolist()
        cache.set("stock:codes", codes, ttl=86400 * 3)
        
        print(f"[{datetime.now()}] 缓存完成：共 {len(codes)} 只主板股票")
         
    except Exception as e:
        print(f"[{datetime.now()}] 程序运行出错：{str(e)}")
        import traceback
        traceback.print_exc()
