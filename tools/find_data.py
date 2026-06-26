import tushare as ts
import datetime
from rediscache import RedisCache
import os
from langchain_core.tools import tool, BaseTool

cache = RedisCache(password=os.getenv("REDIS_PASSWORD", ""))

def match_conditions(price_str):
    """判断价格字符串是否符合任一条件，价格必须为有效浮点数"""
    try:
        p = float(price_str)
    except (ValueError, TypeError):
        return False
    cents = int(round(p * 100))  # 总金额的"分"数
    decimal_part = cents % 100   # 两位整数，范围 0~99
    # 条件1：小数部分重复（十位==个位，即余数两位数字相同）
    if (decimal_part // 10) == (decimal_part % 10):
        return True
    return False

@tool
def find_special_stocks() -> str:
    """获取当前市场中值得关注的"特殊股票"列表，通常包括异动股（如涨跌幅异常、成交量突变、资金大幅流入流出、换手率激增等）。返回结果附带基本的量价特征与异动标签。"""
    codes = cache.get("stock:codes")
    if not codes:
        return "缓存中无股票代码，请稍后重试。"

    result = []
    for code in codes:
        data = cache.hgetall(f"stock:spot:{code}")
        if not data:
            continue
        pct = float(data.get('pct_chg', 0))
        up_days = int(data.get('up_days', 0))
        if up_days > 2 and pct > 2 and pct <= 7:
            low = data.get('low', '')
            # 最低价满足条件即选入
            if match_conditions(low):
                result.append(('股票代码', code,
                                '交易日期', data.get('trade_date'),
                                '最高价', data.get('high'),
                                '开盘价', data.get('open'),
                                '最低价', data.get('low'),
                                '收盘价', data.get('close'),
                                '昨收', data.get('pre_close'),
                                '涨跌额', data.get('change'),
                                '涨跌幅', data.get('pct_chg'),
                                '成交量', data.get('vol'),
                                '成交额', data.get('amount'),
                                '连涨天数', data.get('up_days')
                ))

    if not result:
        return "当前暂无符合条件的特殊股票。"

    return result
