import pandas as pd
from datetime import datetime, timedelta
import tushare as ts
from rediscache import RedisCache
import requests
import os
from langchain_core.tools import tool, BaseTool

today = datetime.now().strftime("%Y%m%d")                # 当日日期
start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")  # 回溯10天，覆盖足够交易日
pro = ts.pro_api(os.getenv("TUSHARE_TOKEN"))

@tool
def fetch_stock_data(code: str) -> str:
    """获取指定股票的近十日日线数据，包括开盘价、收盘价、最高价、最低价、成交量、成交额、涨跌幅、涨跌额等。请使用标准股票代码如 000001.SZ。"""
    # 拉取指定股票日线
    df = pro.daily(ts_code=code, start_date=start_date, end_date=today,
                   fields="ts_code,trade_date,high,open,low,close,pre_close,pct_chg,vol,amount,change")
    if df.empty:
        return f"[{datetime.now()}] 当日无数据"
    return df.to_dict(orient="records")
