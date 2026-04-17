import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="中美股市连涨+资金流+小市值Alpha监控", layout="wide")
st.title("🇺🇸 美股 & 🇨🇳 A股 3日/5日连涨 + 资金流向 + 小市值Alpha监控系统（龙头+成长版）")
st.markdown("**已大幅扩展**：板块/个股数量增加3倍以上 | 美股全部带中文名+板块 | 新增资金流入强度 | 新增小市值稳健成长Alpha监控（慢牛、非爆拉）")

# ====================== 扩展配置（大幅增加数量） ======================
US_SECTORS = {  # 板块ETF（用于资金流向参考）
    "科技": "XLK", "半导体": "SMH", "金融": "XLF", "医疗保健": "XLV",
    "能源": "XLE", "可选消费": "XLY", "工业": "XLI", "必需消费": "XLP",
    "公用事业": "XLU", "材料": "XLB", "房地产": "XLRE", "通信服务": "XLC",
    "新能源": "ICLN", "人工智能": "BOTZ", "云计算": "SKYY"
}

# 美股个股（大幅扩展 + 中文名 + 板块属性）
US_STOCKS = {
    "NVDA": {"cn": "英伟达", "sector": "科技/半导体"},
    "AAPL": {"cn": "苹果", "sector": "科技"},
    "MSFT": {"cn": "微软", "sector": "科技/云计算"},
    "GOOGL": {"cn": "谷歌", "sector": "通信"},
    "AMZN": {"cn": "亚马逊", "sector": "可选消费"},
    "META": {"cn": "Meta", "sector": "通信"},
    "TSLA": {"cn": "特斯拉", "sector": "新能源/汽车"},
    "AVGO": {"cn": "博通", "sector": "半导体"},
    "LLY": {"cn": "礼来", "sector": "医药"},
    "JPM": {"cn": "摩根大通", "sector": "金融"},
    "AMD": {"cn": "超微半导体", "sector": "半导体"},
    "ASML": {"cn": "阿斯麦", "sector": "半导体"},
    "COST": {"cn": "好市多", "sector": "必需消费"},
    "V": {"cn": "维萨", "sector": "金融"},
    "MA": {"cn": "万事达", "sector": "金融"},
    "UNH": {"cn": "联合健康", "sector": "医药"},
    "BAC": {"cn": "美国银行", "sector": "金融"},
    "WMT": {"cn": "沃尔玛", "sector": "必需消费"},
    "ARM": {"cn": "Arm", "sector": "科技"},
    "SMCI": {"cn": "超微电脑", "sector": "科技"},
    "PLTR": {"cn": "Palantir", "sector": "科技"},
    "CRWD": {"cn": "CrowdStrike", "sector": "科技"},
    "NOW": {"cn": "ServiceNow", "sector": "云计算"}
}

# A股龙头个股（大幅扩展，按板块分组）
A_LEADERS = {
    "白酒/消费": ["sh600519"],                    # 贵州茅台
    "新能源/电池": ["sz300750", "sz002594", "sh601012"],  # 宁德时代、比亚迪、隆基绿能
    "半导体/科技": ["sh688981", "sz300782", "sh688041"],  # 中芯国际、卓胜微、芯原股份
    "医药": ["sh600276", "sh600196"],                     # 恒瑞医药、复星医药
    "家电/消费": ["sz000333", "sz000651", "sz000725"],    # 美的、格力、海信家电
    "银行/金融": ["sh601398", "sh601288", "sh601166"],    # 工行、农行、兴业银行
    "汽车/智能驾驶": ["sz002594", "sh600104"],            # 比亚迪、上汽集团
    "光伏/新能源": ["sh601012", "sh600438"],              # 隆基、通威股份
    "钢铁/周期": ["sh600019", "sh600010"]                 # 宝钢、包钢
}

# 小市值Alpha候选个股（用于慢牛监控，美股用动态市值过滤，A股用固定中小市值热门）
US_SMALL_CAP_CANDIDATES = ["ARM", "SMCI", "PLTR", "CRWD", "NOW", "SOFI", "RIVN", "LCID", "PATH", "U", "SNOW", "DDOG"]
A_SMALL_CAP_CANDIDATES = ["sz300782", "sh688041", "sz002594", "sh688981", "sz300750", "sh600438"]  # 部分中小市值成长股

# ====================== 数据获取函数（新增Volume支持） ======================
@st.cache_data(ttl=1800)
def fetch_us_data(ticker: str, period="120d"):
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 10:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, axis=1, level=1) if len(df.columns.levels) > 1 else df
        df = df[['Close', 'Volume']].rename(columns={"Close": "close", "Volume": "volume"})
        return df
    except:
        return None

@st.cache_data(ttl=1800)
def fetch_us_info(ticker: str):
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        return {
            "marketCap": info.get("marketCap", None),
            "regularMarketPrice": info.get("regularMarketPrice", None)
        }
    except:
        return None

@st.cache_data(ttl=1800)
def fetch_a_data(symbol: str):
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=200"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        if not text.startswith("["):
            return None
        data = json.loads(text)
        if not data or len(data) < 10:
            return None
        df = pd.DataFrame(data)
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["day", "close", "volume"]]
    except:
        return None

def calculate_metrics(df, is_us=True):
    """同时计算3/5日连涨 + 资金流入强度（成交量放大率）"""
    if df is None or len(df) < 10:
        return None, None, 0, 0, 0, None, None

    closes = df["close"].values
    volumes = df["volume"].values
    latest_close = closes[-1]

    ret3 = round((latest_close / closes[-4] - 1) * 100, 2) if len(closes) >= 4 else None
    ret5 = round((latest_close / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else None

    # 当前连涨天数
    current_streak = 0
    for i in range(len(closes)-1, 0, -1):
        if closes[i] > closes[i-1] + 1e-6:
            current_streak += 1
        else:
            break

    streak3 = sum(1 for i in range(-3, 0) if closes[i] > closes[i-1] + 1e-6) if len(closes) >= 3 else 0
    streak5 = sum(1 for i in range(-5, 0) if closes[i] > closes[i-1] + 1e-6) if len(closes) >= 5 else 0

    # 资金流入强度（成交量放大率）：最近5日平均成交量 vs 前5日
    if len(volumes) >= 10:
        avg_vol_recent = np.mean(volumes[-5:])
        avg_vol_prev = np.mean(volumes[-10:-5])
        vol_strength = round((avg_vol_recent / avg_vol_prev - 1) * 100, 2) if avg_vol_prev > 0 else 0
    else:
        vol_strength = None

    return ret3, ret5, streak3, streak5, current_streak, vol_strength, latest_close

def is_small_cap_alpha(df, market_cap=None, is_us=True):
    """小市值稳健Alpha判断：慢牛、非爆拉、量价齐升"""
    if df is None or len(df) < 60:
        return False, None, None, None
    closes = df["close"].values
    volumes = df["volume"].values

    # 过去6个月涨幅（温和上涨）
    ret_6m = (closes[-1] / closes[-120] - 1) * 100 if len(closes) >= 120 else (closes[-1] / closes[0] - 1) * 100
    if not (15 < ret_6m < 150):  # 15%-150% 慢牛区间
        return False, ret_6m, None, None

    # 波动率低（非爆拉）
    daily_ret = np.diff(closes) / closes[:-1]
    volatility = np.std(daily_ret[-60:]) * 100  # 最近60日年化波动率近似
    if volatility > 3.0:  # 日波动率 >3% 视为高波动，排除
        return False, ret_6m, volatility, None

    # 成交量趋势上升
    vol_trend = np.mean(volumes[-30:]) / np.mean(volumes[-90:-60]) - 1 if len(volumes) >= 90 else 0
    vol_trend_pct = round(vol_trend * 100, 2)

    # 市值过滤（美股动态，A股预设）
    if is_us and market_cap and market_cap > 10_000_000_000:  # <100亿美金视为小市值
        return False, ret_6m, volatility, vol_trend_pct

    return True, ret_6m, volatility, vol_trend_pct

# ====================== 主界面 ======================
tabs = st.tabs(["🇺🇸 美股板块", "🇺🇸 美股个股", "🇨🇳 A股个股", "💰 资金流向排行", "📈 小市值Alpha监控", "🔄 共振对比"])

# 1. 美股板块
with tabs[0]:
    st.subheader("美股板块（Sector ETFs） - 3/5日连涨")
    data_list = []
    for name, ticker in US_SECTORS.items():
        df = fetch_us_data(ticker)
        ret3, ret5, s3, s5, curr, vol_str, _ = calculate_metrics(df)
        if df is not None:
            latest = round(df["close"].iloc[-1], 2)
            data_list.append({
                "板块": name, "代码": ticker, "最新价": latest,
                "3日涨幅%": ret3, "5日涨幅%": ret5,
                "3日连涨": s3, "5日连涨": s5, "当前连涨": curr,
                "资金流入强度%": vol_str
            })
    if data_list:
        df_sector = pd.DataFrame(data_list)
        st.dataframe(df_sector, use_container_width=True, hide_index=True)
    else:
        st.warning("暂无板块数据")

# 2. 美股个股（新增中文名 + 板块 + 市值）
with tabs[1]:
    st.subheader("美股龙头个股（扩展版）")
    data_list = []
    for ticker, info in US_STOCKS.items():
        df = fetch_us_data(ticker)
        ret3, ret5, s3, s5, curr, vol_str, latest_price = calculate_metrics(df)
        info_data = fetch_us_info(ticker)
        market_cap = info_data.get("marketCap") if info_data else None
        market_cap_str = f"{market_cap/1e9:.1f}B" if market_cap else "N/A"
        if df is not None:
            data_list.append({
                "个股": ticker,
                "中文名": info["cn"],
                "所属板块": info["sector"],
                "最新价": round(latest_price, 2),
                "市值": market_cap_str,
                "3日涨幅%": ret3, "5日涨幅%": ret5,
                "3日连涨": s3, "5日连涨": s5, "当前连涨": curr,
                "资金流入强度%": vol_str
            })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
    else:
        st.warning("暂无个股数据")

# 3. A股个股
with tabs[2]:
    st.subheader("A股龙头个股（扩展版）")
    data_list = []
    name_map = {
        "sh600519": "贵州茅台", "sz300750": "宁德时代", "sz002594": "比亚迪",
        "sh688981": "中芯国际", "sz300782": "卓胜微", "sh600276": "恒瑞医药",
        "sz000333": "美的集团", "sz000651": "格力电器", "sh601398": "工商银行",
        "sh601288": "农业银行", "sh601012": "隆基绿能", "sh600196": "复星医药",
        "sh600104": "上汽集团", "sh600438": "通威股份", "sh600019": "宝钢股份"
    }
    for sector_name, symbols in A_LEADERS.items():
        for sym in symbols:
            df = fetch_a_data(sym)
            ret3, ret5, s3, s5, curr, vol_str, latest_price = calculate_metrics(df, is_us=False)
            if df is not None:
                data_list.append({
                    "板块": sector_name,
                    "个股": name_map.get(sym, sym),
                    "代码": sym,
                    "最新价": round(latest_price, 2),
                    "3日涨幅%": ret3, "5日涨幅%": ret5,
                    "3日连涨": s3, "5日连涨": s5, "当前连涨": curr,
                    "资金流入强度%": vol_str
                })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
    else:
        st.warning("暂无A股数据")

# 4. 资金流向排行（新功能）
with tabs[3]:
    st.subheader("💰 资金流向强度排行（成交量放大+连涨）")
    st.markdown("**资金流入强度** = 最近5日平均成交量较前5日放大百分比（越高越强）")
    all_flow = []
    # 美股板块
    for name, ticker in US_SECTORS.items():
        df = fetch_us_data(ticker)
        _, _, _, _, _, vol_str, _ = calculate_metrics(df)
        if vol_str is not None and vol_str > 10:
            all_flow.append({"市场": "🇺🇸 美股", "名称": name, "资金流入强度%": vol_str, "类型": "板块"})
    # 美股个股
    for ticker, info in US_STOCKS.items():
        df = fetch_us_data(ticker)
        _, _, _, _, _, vol_str, _ = calculate_metrics(df)
        if vol_str is not None and vol_str > 15:
            all_flow.append({"市场": "🇺🇸 美股", "名称": f"{info['cn']}({ticker})", "资金流入强度%": vol_str, "类型": "个股"})
    # A股
    for sector_name, symbols in A_LEADERS.items():
        for sym in symbols:
            df = fetch_a_data(sym)
            _, _, _, _, _, vol_str, _ = calculate_metrics(df, is_us=False)
            if vol_str is not None and vol_str > 20:
                all_flow.append({"市场": "🇨🇳 A股", "名称": name_map.get(sym, sym), "资金流入强度%": vol_str, "类型": "个股"})
    if all_flow:
        df_flow = pd.DataFrame(all_flow).sort_values("资金流入强度%", ascending=False)
        st.dataframe(df_flow, use_container_width=True, hide_index=True)
    else:
        st.info("暂无明显资金流入信号")

# 5. 小市值Alpha监控（新功能）
with tabs[4]:
    st.subheader("📈 小市值稳健Alpha监控（慢牛成长股）")
    st.markdown("**筛选逻辑**：市值<100亿美金（美股）| 6个月温和上涨15-150% | 低波动 | 成交量趋势上升 | 非爆拉")

    # 美股小市值
    st.write("**🇺🇸 美股小市值稳健Alpha**")
    alpha_list = []
    for ticker in US_SMALL_CAP_CANDIDATES:
        df = fetch_us_data(ticker, period="1y")
        info = fetch_us_info(ticker)
        market_cap = info.get("marketCap") if info else None
        is_alpha, ret6m, vola, vol_trend = is_small_cap_alpha(df, market_cap, is_us=True)
        if is_alpha and df is not None:
            alpha_list.append({
                "个股": ticker,
                "中文名": US_STOCKS.get(ticker, {}).get("cn", ticker),
                "市值": f"{market_cap/1e9:.1f}B" if market_cap else "N/A",
                "6个月涨幅%": round(ret6m, 2),
                "波动率%": round(vola, 2),
                "成交量趋势%": vol_trend
            })
    if alpha_list:
        st.dataframe(pd.DataFrame(alpha_list), use_container_width=True, hide_index=True)
    else:
        st.info("当前暂无符合慢牛Alpha的美股")

    # A股小市值（简化版，基于扩展列表+成交量趋势）
    st.write("**🇨🇳 A股小市值稳健Alpha**（市值近似判断）")
    a_alpha_list = []
    for sym in A_SMALL_CAP_CANDIDATES:
        df = fetch_a_data(sym)
        _, _, _, _, _, vol_str, _ = calculate_metrics(df, is_us=False)
        if df is not None and len(df) >= 120:
            ret6m = round((df["close"].iloc[-1] / df["close"].iloc[-120] - 1) * 100, 2)
            if 15 < ret6m < 150 and vol_str and vol_str > 15:
                a_alpha_list.append({
                    "个股": name_map.get(sym, sym),
                    "代码": sym,
                    "6个月涨幅%": ret6m,
                    "资金流入强度%": vol_str
                })
    if a_alpha_list:
        st.dataframe(pd.DataFrame(a_alpha_list), use_container_width=True, hide_index=True)
    else:
        st.info("当前暂无符合慢牛Alpha的A股")

# 6. 共振对比
with tabs[5]:
    st.subheader("🔄 中美市场共振对比")
    st.info("当同一主题（科技、新能源、金融等）在**资金流入强度**、**连涨**、**小市值Alpha**同时出现，即为强共振信号！")

st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：雅虎财经 + 新浪财经 | 非投资建议")

if st.button("🔄 刷新全部数据（清除缓存）"):
    st.cache_data.clear()
    st.rerun()
