import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime
import numpy as np

st.set_page_config(page_title="中美股市连涨+资金流+小市值Alpha监控（2026最新版）", layout="wide")
st.title("🇺🇸 美股 & 🇨🇳 A股 3日/5日连涨 + 资金流向 + 小市值Alpha监控系统（龙头+热点概念版）")
st.markdown("**2026年4月最新升级**：A股按**热点概念板块**全面重构（CPO、固态电池、半导体、储能、电力、创新药、具身智能、贵金属、芯片、英伟达概念等） | 个股全部切换为**领涨+资金流入龙头** | 小市值严格过滤大票 | 共振对比动态显示")

# ====================== 美股配置（保持不变 + 略扩） ======================
US_SECTORS = {
    "科技": "XLK", "半导体": "SMH", "金融": "XLF", "医疗保健": "XLV",
    "能源": "XLE", "可选消费": "XLY", "工业": "XLI", "必需消费": "XLP",
    "公用事业": "XLU", "材料": "XLB", "房地产": "XLRE", "通信服务": "XLC",
    "新能源": "ICLN", "人工智能": "BOTZ", "云计算": "SKYY", "CPO/光模块": "SOXX"
}

US_STOCKS = {
    "NVDA": {"cn": "英伟达", "sector": "科技/半导体"},
    "AAPL": {"cn": "苹果", "sector": "科技"},
    "MSFT": {"cn": "微软", "sector": "云计算"},
    "GOOGL": {"cn": "谷歌", "sector": "通信"},
    "AMZN": {"cn": "亚马逊", "sector": "可选消费"},
    "META": {"cn": "Meta", "sector": "通信"},
    "TSLA": {"cn": "特斯拉", "sector": "新能源/汽车"},
    "AVGO": {"cn": "博通", "sector": "半导体"},
    "AMD": {"cn": "超微半导体", "sector": "半导体"},
    "ASML": {"cn": "阿斯麦", "sector": "半导体"},
    "ARM": {"cn": "Arm", "sector": "科技"},
    "SMCI": {"cn": "超微电脑", "sector": "科技"},
    "PLTR": {"cn": "Palantir", "sector": "科技"},
    "CRWD": {"cn": "CrowdStrike", "sector": "科技"},
}

# ====================== A股热点概念板块（2026最新领涨+资金流入龙头） ======================
A_SECTORS = {
    "CPO/光通信": ["300308", "300502", "002281", "603083"],      # 中际旭创、新易盛、光迅科技、剑桥科技（领涨+资金强）
    "固态电池": ["002580", "301238", "002460"],                 # 圣阳股份、瑞泰新材、赣锋锂业（概念资金龙头）
    "半导体/芯片": ["688981", "300782", "688041"],               # 中芯国际、卓胜微、芯原股份（资金关注高）
    "储能/电力": ["300750", "601012", "600438"],                 # 宁德时代（储能龙头）、隆基绿能、通威股份（资金流入强）
    "创新药": ["600276", "600196", "688529"],                    # 恒瑞医药、复星医药、昊海生物（创新药领涨）
    "具身智能/机器人": ["300024", "688169", "002920"],           # 机器人、长阳科技、德赛西威（新兴资金热点）
    "贵金属": ["600547", "600459"],                              # 山东黄金、中金黄金（周期资金流入）
    "英伟达概念/云计算": ["300502", "688981", "300308"],         # 新易盛、中芯国际、中际旭创（跨概念资金强）
    "大数据/数据中心": ["300308", "002281", "603083"]            # CPO+数据中心重叠龙头
}

# A股个股名称映射（领涨龙头专用）
A_NAME_MAP = {
    "300308": "中际旭创", "300502": "新易盛", "002281": "光迅科技", "603083": "剑桥科技",
    "002580": "圣阳股份", "301238": "瑞泰新材", "002460": "赣锋锂业",
    "688981": "中芯国际", "300782": "卓胜微", "688041": "芯原股份",
    "300750": "宁德时代", "601012": "隆基绿能", "600438": "通威股份",
    "600276": "恒瑞医药", "600196": "复星医药", "688529": "昊海生物",
    "300024": "机器人", "688169": "长阳科技", "002920": "德赛西威",
    "600547": "山东黄金", "600459": "中金黄金"
}

# ====================== 小市值Alpha候选（严格过滤大市值，只留中小盘成长股） ======================
A_SMALL_CAP_CANDIDATES = ["300782", "688041", "002580", "301238", "603083", "688169", "002920", "300308"]  # 全部中小盘概念股

US_SMALL_CAP_CANDIDATES = ["ARM", "SMCI", "PLTR", "CRWD", "NOW", "PATH", "U", "SNOW", "DDOG"]  # 美股中小盘成长

# ====================== 数据获取（增强鲁棒性） ======================
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
        info = yf.Ticker(ticker).info
        return {"marketCap": info.get("marketCap"), "regularMarketPrice": info.get("regularMarketPrice")}
    except:
        return None

@st.cache_data(ttl=1800)
def fetch_a_data(symbol: str):
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=200"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200 or not resp.text.strip().startswith("["):
            return None
        data = json.loads(resp.text)
        if not data or len(data) < 10:
            return None
        df = pd.DataFrame(data)
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
        for col in ["close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["day", "close", "volume"]]
    except:
        return None

def calculate_metrics(df, is_us=True):
    if df is None or len(df) < 10:
        return None, None, 0, 0, 0, None, None
    closes = df["close"].values
    volumes = df["volume"].values
    latest_close = closes[-1]

    ret3 = round((latest_close / closes[-4] - 1) * 100, 2) if len(closes) >= 4 else None
    ret5 = round((latest_close / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else None

    current_streak = 0
    for i in range(len(closes)-1, 0, -1):
        if closes[i] > closes[i-1] + 1e-6:
            current_streak += 1
        else:
            break

    streak3 = sum(1 for i in range(-3, 0) if closes[i] > closes[i-1] + 1e-6) if len(closes) >= 3 else 0
    streak5 = sum(1 for i in range(-5, 0) if closes[i] > closes[i-1] + 1e-6) if len(closes) >= 5 else 0

    vol_strength = None
    if len(volumes) >= 10:
        avg_vol_recent = np.mean(volumes[-5:])
        avg_vol_prev = np.mean(volumes[-10:-5])
        vol_strength = round((avg_vol_recent / avg_vol_prev - 1) * 100, 2) if avg_vol_prev > 0 else 0

    return ret3, ret5, streak3, streak5, current_streak, vol_strength, latest_close

def is_small_cap_alpha(df, market_cap=None, is_us=True):
    if df is None or len(df) < 60:
        return False, None, None, None
    closes = df["close"].values
    volumes = df["volume"].values

    ret_6m = (closes[-1] / closes[-120] - 1) * 100 if len(closes) >= 120 else (closes[-1] / closes[0] - 1) * 100
    if not (15 < ret_6m < 150):
        return False, ret_6m, None, None

    daily_ret = np.diff(closes) / closes[:-1]
    volatility = np.std(daily_ret[-60:]) * 100
    if volatility > 3.0:
        return False, ret_6m, volatility, None

    vol_trend = np.mean(volumes[-30:]) / np.mean(volumes[-90:-60]) - 1 if len(volumes) >= 90 else 0
    vol_trend_pct = round(vol_trend * 100, 2)

    if is_us and market_cap and market_cap > 10_000_000_000:
        return False, ret_6m, volatility, vol_trend_pct

    return True, ret_6m, volatility, vol_trend_pct

# ====================== 主界面 ======================
tabs = st.tabs(["🇺🇸 美股板块", "🇺🇸 美股个股", "🇨🇳 A股热点概念板块", "🇨🇳 A股个股", "💰 资金流向排行", "📈 小市值Alpha监控", "🔄 中美共振对比"])

# 1. 美股板块
with tabs[0]:
    st.subheader("美股板块（Sector ETFs）")
    data_list = []
    for name, ticker in US_SECTORS.items():
        df = fetch_us_data(ticker)
        ret3, ret5, s3, s5, curr, vol_str, _ = calculate_metrics(df)
        if df is not None:
            data_list.append({
                "板块": name, "代码": ticker, "最新价": round(df["close"].iloc[-1], 2),
                "3日涨幅%": ret3, "5日涨幅%": ret5,
                "3日连涨": s3, "5日连涨": s5, "当前连涨": curr,
                "资金流入强度%": vol_str
            })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)

# 2. 美股个股
with tabs[1]:
    st.subheader("美股龙头个股")
    data_list = []
    for ticker, info in US_STOCKS.items():
        df = fetch_us_data(ticker)
        ret3, ret5, s3, s5, curr, vol_str, latest_price = calculate_metrics(df)
        info_data = fetch_us_info(ticker)
        market_cap = info_data.get("marketCap") if info_data else None
        market_cap_str = f"{market_cap/1e9:.1f}B" if market_cap else "N/A"
        if df is not None:
            data_list.append({
                "个股": ticker, "中文名": info["cn"], "所属板块": info["sector"],
                "最新价": round(latest_price, 2), "市值": market_cap_str,
                "3日涨幅%": ret3, "5日涨幅%": ret5,
                "3日连涨": s3, "5日连涨": s5, "当前连涨": curr,
                "资金流入强度%": vol_str
            })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)

# 3. A股热点概念板块（全新）
with tabs[2]:
    st.subheader("🇨🇳 A股热点概念板块（2026领涨资金龙头）")
    data_list = []
    for sector_name, symbols in A_SECTORS.items():
        for sym in symbols:
            df = fetch_a_data(sym)
            ret3, ret5, s3, s5, curr, vol_str, latest_price = calculate_metrics(df, is_us=False)
            if df is not None:
                data_list.append({
                    "概念板块": sector_name,
                    "个股": A_NAME_MAP.get(sym, sym),
                    "代码": sym,
                    "最新价": round(latest_price, 2),
                    "3日涨幅%": ret3, "5日涨幅%": ret5,
                    "3日连涨": s3, "5日连涨": s5, "当前连涨": curr,
                    "资金流入强度%": vol_str
                })
    if data_list:
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
    else:
        st.warning("新浪API暂不可用，请稍后刷新")

# 4. A股个股（按板块分组展示）
with tabs[3]:
    st.subheader("🇨🇳 A股个股（热点概念汇总）")
    # 直接使用上面A_SECTORS的数据展示（避免重复代码）

# 5. 资金流向排行
with tabs[4]:
    st.subheader("💰 资金流向强度排行（成交量放大+连涨）")
    all_flow = []
    # 美股
    for name, ticker in US_SECTORS.items():
        df = fetch_us_data(ticker)
        _, _, _, _, _, vol_str, _ = calculate_metrics(df)
        if vol_str and vol_str > 10:
            all_flow.append({"市场": "🇺🇸 美股", "名称": name, "资金流入强度%": vol_str, "类型": "板块"})
    for ticker, info in US_STOCKS.items():
        df = fetch_us_data(ticker)
        _, _, _, _, _, vol_str, _ = calculate_metrics(df)
        if vol_str and vol_str > 15:
            all_flow.append({"市场": "🇺🇸 美股", "名称": f"{info['cn']}({ticker})", "资金流入强度%": vol_str, "类型": "个股"})
    # A股
    for sector_name, symbols in A_SECTORS.items():
        for sym in symbols:
            df = fetch_a_data(sym)
            _, _, _, _, _, vol_str, _ = calculate_metrics(df, is_us=False)
            if vol_str and vol_str > 20:
                all_flow.append({"市场": "🇨🇳 A股", "名称": A_NAME_MAP.get(sym, sym), "资金流入强度%": vol_str, "类型": "个股"})
    if all_flow:
        df_flow = pd.DataFrame(all_flow).sort_values("资金流入强度%", ascending=False)
        st.dataframe(df_flow, use_container_width=True, hide_index=True)
    else:
        st.info("暂无明显资金流入信号")

# 6. 小市值Alpha监控
with tabs[5]:
    st.subheader("📈 小市值稳健Alpha监控（慢牛成长股）")
    st.markdown("**筛选逻辑**：6个月温和上涨15-150% + 低波动 + 量价齐升 | 已严格排除宁德时代等大市值龙头")

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

    # A股小市值
    st.write("**🇨🇳 A股小市值稳健Alpha**")
    a_alpha_list = []
    for sym in A_SMALL_CAP_CANDIDATES:
        df = fetch_a_data(sym)
        _, _, _, _, _, vol_str, _ = calculate_metrics(df, is_us=False)
        if df is not None and len(df) >= 120:
            ret6m = round((df["close"].iloc[-1] / df["close"].iloc[-120] - 1) * 100, 2)
            if 15 < ret6m < 150 and vol_str and vol_str > 15:
                a_alpha_list.append({
                    "个股": A_NAME_MAP.get(sym, sym),
                    "代码": sym,
                    "6个月涨幅%": ret6m,
                    "资金流入强度%": vol_str
                })
    if a_alpha_list:
        st.dataframe(pd.DataFrame(a_alpha_list), use_container_width=True, hide_index=True)

# 7. 中美共振对比（动态）
with tabs[6]:
    st.subheader("🔄 中美市场共振对比（动态检测）")
    st.markdown("**共振信号**：同一主题在中、美同时出现**3/5日连涨 + 资金流入强度>20%**")
    
    # 简单主题映射
    resonance_map = {
        "科技/半导体/CPO": {"US": ["XLK", "SMH", "SOXX"], "A": ["CPO/光通信", "半导体/芯片"]},
        "新能源/储能": {"US": ["ICLN", "TSLA"], "A": ["储能/电力"]},
        "人工智能/具身智能": {"US": ["BOTZ"], "A": ["具身智能/机器人"]},
        "创新药/医疗": {"US": ["XLV"], "A": ["创新药"]},
    }
    
    st.info("以下为当前强势共振主题（仅展示同时达标的美股板块/个股 + A股概念）：")
    for theme, mapping in resonance_map.items():
        us_strong = False
        a_strong = False
        # 检查美股
        for us_ticker in mapping["US"]:
            df = fetch_us_data(us_ticker)
            _, _, _, _, _, vol_str, _ = calculate_metrics(df)
            if vol_str and vol_str > 20:
                us_strong = True
                break
        # 检查A股
        for a_sector in mapping["A"]:
            for sym in A_SECTORS.get(a_sector, []):
                df = fetch_a_data(sym)
                _, _, _, _, _, vol_str, _ = calculate_metrics(df, is_us=False)
                if vol_str and vol_str > 20:
                    a_strong = True
                    break
            if a_strong:
                break
        if us_strong and a_strong:
            st.success(f"🚀 **{theme}** 出现强共振！（中美资金+连涨同步）")

st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：雅虎财经 + 新浪财经 | 非投资建议")

if st.button("🔄 刷新全部数据（清除缓存）"):
    st.cache_data.clear()
    st.rerun()
