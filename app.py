import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime

st.set_page_config(page_title="中美股市连涨监控 - 龙头共振", layout="wide")
st.title("🇺🇸 美股 & 🇨🇳 A股 3/5日持续增长监控系统")
st.markdown("**只关注龙头板块和个股**（小票大拉大砸忽略）。美股用雅虎财经 API，A股用新浪财经 K线 API。")

# ====================== 配置 ======================
st.sidebar.header("监控设置")
streak_days = st.sidebar.selectbox("连涨天数", [3, 5], index=0)
refresh = st.sidebar.button("🔄 刷新所有数据")

# 美股板块（Sector ETFs） - 龙头板块代理
US_SECTORS = {
    "科技": "XLK",
    "金融": "XLF",
    "医疗保健": "XLV",
    "能源": "XLE",
    "可选消费": "XLY",
    "工业": "XLI",
    "必需消费": "XLP",
    "公用事业": "XLU",
    "材料": "XLB",
    "房地产": "XLRE",
    "通信服务": "XLC",
}

# 美股龙头个股（部分代表）
US_LEADERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "LLY", "JPM"]

# A股龙头个股（symbol 格式：sh600519 / sz300750）
A_LEADERS = {
    "白酒/消费": ["sh600519"],           # 贵州茅台
    "新能源/电池": ["sz300750", "sz002594"],  # 宁德时代、比亚迪
    "半导体/科技": ["sh688981", "sz300782"], # 中芯国际、某半导体
    "医药": ["sh600276"],                 # 恒瑞医药
    "家电": ["sz000333", "sz000651"],     # 美的集团、格力电器
    "银行": ["sh601398", "sh601288"],     # 工商银行、农业银行
    # 可自行继续添加更多龙头
}

# ====================== 数据获取函数 ======================
@st.cache_data(ttl=3600)  # 1小时缓存
def fetch_us_data(ticker: str, days: int = 30):
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return None
        return df[['Close']].rename(columns={"Close": "close"})
    except:
        return None

@st.cache_data(ttl=3600)
def fetch_a_data(symbol: str, datalen: int = 60):
    """新浪财经日K线 API (scale=240 = 日线)"""
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={datalen}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        data = json.loads(text) if text.startswith("[") else []
        if not data:
            return None
        df = pd.DataFrame(data)
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["day", "close"]]
    except Exception as e:
        st.error(f"新浪API错误 {symbol}: {e}")
        return None

def get_streak_and_returns(df, is_us=True):
    """返回 3日/5日涨跌幅 + 当前连涨天数"""
    if df is None or len(df) < 6:
        return None, None, 0
    closes = df["close"].values
    # 最近收盘价
    latest_close = closes[-1]
    # 3日/5日涨幅（需要前4/6个数据）
    ret3 = round((latest_close / closes[-4] - 1) * 100, 2) if len(closes) >= 4 else None
    ret5 = round((latest_close / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else None
    # 连涨天数（最后连续正收益天数）
    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1]:
            streak += 1
        else:
            break
    return ret3, ret5, streak

# ====================== 主界面 ======================
tab_us, tab_a, tab_compare = st.tabs(["🇺🇸 美股监控", "🇨🇳 A股监控", "🔄 共振对比"])

with tab_us:
    st.subheader("美股 - 板块（Sector ETFs）")
    sector_data = []
    for name, ticker in US_SECTORS.items():
        df = fetch_us_data(ticker)
        ret3, ret5, streak = get_streak_and_returns(df, is_us=True)
        if ret3 is not None and streak >= streak_days:
            sector_data.append({
                "板块": name,
                "代码": ticker,
                "最新价": round(df["close"].iloc[-1], 2) if df is not None else None,
                f"{streak_days}日连涨": "✅ 是",
                "3日涨幅%": ret3,
                "5日涨幅%": ret5,
                "连涨天数": streak
            })
    if sector_data:
        st.dataframe(pd.DataFrame(sector_data), use_container_width=True)
    else:
        st.info("暂无符合条件的美股板块")

    st.subheader("美股 - 龙头个股")
    leader_data = []
    for ticker in US_LEADERS:
        df = fetch_us_data(ticker)
        ret3, ret5, streak = get_streak_and_returns(df, is_us=True)
        if ret3 is not None and streak >= streak_days:
            leader_data.append({
                "个股": ticker,
                "最新价": round(df["close"].iloc[-1], 2) if df is not None else None,
                f"{streak_days}日连涨": "✅ 是",
                "3日涨幅%": ret3,
                "5日涨幅%": ret5,
                "连涨天数": streak
            })
    if leader_data:
        st.dataframe(pd.DataFrame(leader_data), use_container_width=True)
    else:
        st.info("暂无符合条件的美股龙头个股")

with tab_a:
    st.subheader("A股 - 龙头个股（按板块分组）")
    a_data = []
    for sector_name, symbols in A_LEADERS.items():
        for sym in symbols:
            df = fetch_a_data(sym)
            ret3, ret5, streak = get_streak_and_returns(df, is_us=False)
            if ret3 is not None and streak >= streak_days:
                name_map = {"sh600519": "贵州茅台", "sz300750": "宁德时代", "sz002594": "比亚迪",
                            "sh688981": "中芯国际", "sz300782": "卓胜微", "sh600276": "恒瑞医药",
                            "sz000333": "美的集团", "sz000651": "格力电器", "sh601398": "工商银行",
                            "sh601288": "农业银行"}  # 可继续扩展
                a_data.append({
                    "板块": sector_name,
                    "个股": name_map.get(sym, sym),
                    "代码": sym,
                    "最新价": round(df["close"].iloc[-1], 2) if df is not None else None,
                    f"{streak_days}日连涨": "✅ 是",
                    "3日涨幅%": ret3,
                    "5日涨幅%": ret5,
                    "连涨天数": streak
                })
    if a_data:
        st.dataframe(pd.DataFrame(a_data), use_container_width=True)
    else:
        st.info("暂无符合条件的A股龙头个股")

with tab_compare:
    st.subheader("中美市场共振对比")
    st.markdown("**共振判断逻辑**：同一主题板块/龙头同时出现连涨（科技、新能源、消费、金融等）。")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**美股 rising 板块/个股**")
        # 简单列出（实际生产可做更智能匹配）
        st.write("科技 → XLK / NVDA 等")
        st.write("新能源/汽车 → TSLA")
        st.write("消费/医疗 → LLY / XLV")
    with col2:
        st.write("**A股 rising 板块/个股**")
        st.write("新能源/电池 → 宁德时代、比亚迪")
        st.write("半导体 → 中芯国际")
        st.write("白酒/消费 → 贵州茅台")
    st.info("👉 手动观察两个市场同时出现“科技/新能源/消费”连涨，即为**共振信号**。可自行扩展映射逻辑。")

# 页脚
st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（美股实时，A股新浪API） | 仅供参考，非投资建议")

if refresh:
    st.cache_data.clear()
    st.rerun()
