import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime

st.set_page_config(page_title="中美股市连涨监控 - 龙头共振", layout="wide")
st.title("🇺🇸 美股 & 🇨🇳 A股 3日/5日持续增长监控系统（龙头版）")
st.markdown("**自动同时显示3日和5日连涨情况** | 只关注龙头板块与个股 | 已修复数据不足导致的崩溃")

# ====================== 配置 ======================
US_SECTORS = {
    "科技": "XLK", "金融": "XLF", "医疗保健": "XLV", "能源": "XLE",
    "可选消费": "XLY", "工业": "XLI", "必需消费": "XLP",
    "公用事业": "XLU", "材料": "XLB", "房地产": "XLRE", "通信服务": "XLC"
}

US_LEADERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "LLY", "JPM"]

A_LEADERS = {
    "白酒/消费": ["sh600519"],                    # 贵州茅台
    "新能源/电池": ["sz300750", "sz002594"],      # 宁德时代、比亚迪
    "半导体/科技": ["sh688981", "sz300782"],      # 中芯国际、卓胜微
    "医药": ["sh600276"],                          # 恒瑞医药
    "家电": ["sz000333", "sz000651"],              # 美的集团、格力电器
    "银行": ["sh601398", "sh601288"]               # 工商银行、农业银行
}

# ====================== 数据获取 ======================
@st.cache_data(ttl=1800)
def fetch_us_data(ticker: str):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        # 处理可能的 MultiIndex 列（新版 yfinance）
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, axis=1, level=1) if len(df.columns.levels) > 1 else df
        if 'Close' in df.columns:
            df = df[['Close']].rename(columns={"Close": "close"})
        elif 'close' not in df.columns:
            return None
        if len(df) < 6:
            return None
        return df
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_a_data(symbol: str):
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=120"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        if not text.startswith("["):
            return None
        data = json.loads(text)
        if not data or len(data) < 6:
            return None
        df = pd.DataFrame(data)
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["day", "close"]]
    except Exception:
        return None

def calculate_streaks(df):
    """安全计算3日和5日涨幅 + 连涨天数"""
    if df is None or len(df) < 6:
        return None, None, 0, 0, 0

    closes = df["close"].values
    if len(closes) < 6:
        return None, None, 0, 0, 0

    latest = closes[-1]

    # 只有数据足够时才计算，避免索引错误
    ret3 = round((latest / closes[-4] - 1) * 100, 2) if len(closes) >= 4 else None
    ret5 = round((latest / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else None

    # 当前连涨天数
    current_streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1] + 1e-6:   # 避免浮点误差
            current_streak += 1
        else:
            break

    # 最近N天连涨天数
    streak3 = sum(1 for i in range(-3, 0) if closes[i] > closes[i - 1] + 1e-6) if len(closes) >= 3 else 0
    streak5 = sum(1 for i in range(-5, 0) if closes[i] > closes[i - 1] + 1e-6) if len(closes) >= 5 else 0

    return ret3, ret5, streak3, streak5, current_streak

# ====================== 主界面 ======================
tabs = st.tabs(["🇺🇸 美股板块", "🇺🇸 美股龙头个股", "🇨🇳 A股龙头个股", "🔄 中美共振对比"])

with tabs[0]:
    st.subheader("美股板块（Sector ETFs）")
    data_list = []
    for name, ticker in US_SECTORS.items():
        df = fetch_us_data(ticker)
        ret3, ret5, s3, s5, curr = calculate_streaks(df)
        if df is not None:
            latest_price = round(df["close"].iloc[-1], 2)
            data_list.append({
                "板块": name, "代码": ticker, "最新价": latest_price,
                "3日涨幅%": ret3, "5日涨幅%": ret5,
                "3日连涨天数": s3, "5日连涨天数": s5,
                "当前连涨天数": curr
            })
    if data_list:
        df_sector = pd.DataFrame(data_list)
        st.dataframe(df_sector, use_container_width=True, hide_index=True)
        st.success(f"共显示 {len(data_list)} 个板块数据")
    else:
        st.warning("暂无美股板块数据（可能网络或 yfinance 临时问题）")

with tabs[1]:
    st.subheader("美股龙头个股")
    data_list = []
    for ticker in US_LEADERS:
        df = fetch_us_data(ticker)
        ret3, ret5, s3, s5, curr = calculate_streaks(df)
        if df is not None:
            latest_price = round(df["close"].iloc[-1], 2)
            data_list.append({
                "个股": ticker, "最新价": latest_price,
                "3日涨幅%": ret3, "5日涨幅%": ret5,
                "3日连涨天数": s3, "5日连涨天数": s5,
                "当前连涨天数": curr
            })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
    else:
        st.warning("暂无美股龙头数据")

with tabs[2]:
    st.subheader("A股龙头个股（按板块分组）")
    data_list = []
    name_map = {
        "sh600519": "贵州茅台", "sz300750": "宁德时代", "sz002594": "比亚迪",
        "sh688981": "中芯国际", "sz300782": "卓胜微", "sh600276": "恒瑞医药",
        "sz000333": "美的集团", "sz000651": "格力电器",
        "sh601398": "工商银行", "sh601288": "农业银行"
    }
    for sector_name, symbols in A_LEADERS.items():
        for sym in symbols:
            df = fetch_a_data(sym)
            ret3, ret5, s3, s5, curr = calculate_streaks(df)
            if df is not None:
                latest_price = round(df["close"].iloc[-1], 2)
                data_list.append({
                    "板块": sector_name,
                    "个股": name_map.get(sym, sym),
                    "代码": sym,
                    "最新价": latest_price,
                    "3日涨幅%": ret3, "5日涨幅%": ret5,
                    "3日连涨天数": s3, "5日连涨天数": s5,
                    "当前连涨天数": curr
                })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
    else:
        st.warning("暂无A股数据（新浪API可能临时不可用）")

with tabs[3]:
    st.subheader("🔄 中美市场共振对比")
    st.markdown("""
    **共振信号参考**：
    - 科技/半导体：美股 XLK / NVDA 与 A股 中芯国际等
    - 新能源/汽车：美股 TSLA 与 A股 宁德时代、比亚迪
    - 消费/医药：美股 XLV / LLY 与 A股 贵州茅台、恒瑞医药
    - 金融：美股 XLF / JPM 与 A股 银行股
    当**同一主题**同时在中美出现较强3日或5日连涨时，即为潜在共振。
    """)
    st.info("建议结合成交量和新闻进一步验证。")

st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 非投资建议")

if st.button("🔄 刷新全部数据（清除缓存）"):
    st.cache_data.clear()
    st.rerun()
