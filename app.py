import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime
import time

# ==========================================
# 1. 本地核心资产库 (防封杀的“外脑”底座)
# ==========================================
# 这里存放的是各产业链最纯正的核心标的（游资和机构公认的龙骨）
# sh代表上海，sz代表深圳
THEMES_DB = {
    "🔥 英伟达/算力产业链 (光模块/液冷/服务器)": [
        "sh601138", "sz300308", "sz300502", "sz000938", "sh600584", "sz300394", "sh603083", "sz002463", "sz300474", "sh600487"
    ], # 工业富联, 中际旭创, 新易盛, 紫光股份, 长电科技, 天孚通信, 剑桥科技, 沪电股份, 景嘉微, 亨通光电
    
    "🤖 具身智能/特斯拉机器人 (减速器/电机/执行器)": [
        "sz002050", "sh600580", "sh603019", "sz002122", "sz002284", "sh603960", "sz300161", "sz002031", "sh601689"
    ], # 三花智控, 绿的谐波, 鸣志电器, 汇川技术, 亚太股份, 克来机电, 华中数控, 巨轮智能, 拓普集团
    
    "🛸 SpaceX/低空经济 (商业航天/飞行汽车)": [
        "sh600862", "sz002389", "sz300993", "sz002985", "sh600118", "sz300589", "sh600391", "sz002380"
    ], # 中航高科, 航天彩虹, 中科星图, 北摩高科, 中国卫星, 江龙船艇, 航发科技, 科大国创
    
    "🛡️ 国家队/低位高股息 (防守反击/汇金底牌)": [
        "sh601088", "sh601988", "sh601288", "sh600900", "sh600028", "sh601006", "sh600104", "sz000338", "sh601111"
    ]  # 中国神华, 中国银行, 农业银行, 长江电力, 中国石化, 大秦铁路, 上汽集团, 潍柴动力, 中国国航
}

# ==========================================
# 2. 数据获取模块：美股隔夜映射 (雅虎财经)
# ==========================================
@st.cache_data(ttl=3600) # 缓存1小时，避免重复请求
def get_us_mapping():
    tickers = {"NVDA": "英伟达(算力)", "TSLA": "特斯拉(机器人)", "AAPL": "苹果(消费电子)", "SPCE": "维珍银河(航天)"}
    us_data = []
    try:
        for ticker, name in tickers.items():
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[0]
                last_close = hist['Close'].iloc[1]
                change_pct = ((last_close - prev_close) / prev_close) * 100
                us_data.append({"标的": name, "最新收盘价": round(last_close, 2), "涨跌幅(%)": round(change_pct, 2)})
        return pd.DataFrame(us_data)
    except Exception as e:
        return pd.DataFrame([{"错误": f"获取美股映射失败: {str(e)}"}])

# ==========================================
# 3. 数据获取模块：腾讯极速批量 API (基本面+量价)
# ==========================================
def fetch_tencent_batch_data(stock_codes):
    """
    通过腾讯财经接口，一次性获取多只股票的实时基本面和量价数据
    腾讯接口神级优势：一秒钟返回PE、PB、总市值和量价，且不封禁云端IP！
    """
    if not stock_codes:
        return pd.DataFrame()
    
    # 将列表拼接成逗号分隔的字符串：'sh601138,sz300308...'
    codes_str = ",".join(stock_codes)
    url = f"http://qt.gtimg.cn/q={codes_str}"
    
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk' # 腾讯接口采用GBK编码
        lines = response.text.strip().split('\n')
        
        results = []
        for line in lines:
            if not line or "=" not in line:
                continue
            # 解析：v_sh601138="1~工业富联~601138~22.50~..."
            data_str = line.split("=")[1].strip('"')
            cols = data_str.split("~")
            
            if len(cols) > 46: # 确保返回了足够的数据字段
                try:
                    results.append({
                        "代码": cols[2],
                        "名称": cols[1],
                        "最新价": float(cols[3]),
                        "涨跌幅(%)": float(cols[32]),     # 字段32：涨跌幅
                        "换手率(%)": float(cols[38]),     # 字段38：换手率
                        "市盈率(PE)": float(cols[39]) if cols[39] else 0.0, # 字段39：动态PE
                        "市净率(PB)": float(cols[46]) if cols[46] else 0.0, # 字段46：PB
                        "总市值(亿)": float(cols[45]) if cols[45] else 0.0  # 字段45：总市值
                    })
                except ValueError:
                    continue
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"腾讯接口请求失败: {e}")
        return pd.DataFrame()

# ==========================================
# 4. Streamlit 界面与主循环
# ==========================================
st.set_page_config(page_title="V2.0 游资顶层架构雷达", layout="wide")

st.markdown("""
### 🦅 V2.0 顶层游资选股雷达 (概念映射 + 腾讯估值 + 极致量价)
**核心逻辑**：摒弃大海捞针，先看隔夜美股指引，锁定 A 股纯正概念核心池，剔除高估值垃圾股，最后抓取低位启动买点。
""")

# --- 模块 A：隔夜美股风向标 ---
st.write("#### 🌍 第一步：隔夜美股风向标 (决定今日主攻叙事)")
us_df = get_us_mapping()
if not us_df.empty and "错误" not in us_df.columns:
    cols = st.columns(len(us_df))
    for idx, row in us_df.iterrows():
        color = "red" if row['涨跌幅(%)'] > 0 else "green"
        arrow = "🔺" if row['涨跌幅(%)'] > 0 else "🔻"
        cols[idx].markdown(f"**{row['标的']}**<br><span style='color:{color}; font-size: 20px;'>{arrow} {row['涨跌幅(%)']}%</span>", unsafe_allow_html=True)
else:
    st.warning("暂无法获取美股映射数据")

st.markdown("---")

# --- 模块 B：漏斗控制台 ---
st.sidebar.header("🎯 核心漏斗设置")

# 漏斗 1：主线选择
selected_theme = st.sidebar.selectbox("1. 锁定今日炒作主线 (核心资产池)", list(THEMES_DB.keys()))

# 漏斗 2：基本面防雷底线
st.sidebar.markdown("**2. 腾讯基本面防雷 (剔除垃圾)**")
max_pe = st.sidebar.slider("剔除高估值 (最大市盈率限制)", 10, 200, 80, help="PE为负(亏损)的会被自动剔除。这里设置上限，拒绝透支炒作。")
require_pb = st.sidebar.checkbox("要求低破净资产防守 (PB < 2)", value=False)

# 漏斗 3：量价极致入场点
st.sidebar.markdown("**3. 量价入场点筛选 (防接盘)**")
min_turnover = st.sidebar.number_input("最小换手率 (%) - 需资金活跃", value=2.0)
max_change = st.sidebar.number_input("最大涨幅限制 (%) - 拒绝追高", value=4.0)
min_change = st.sidebar.number_input("最小涨幅限制 (%) - 底部启动", value=0.0)

# --- 模块 C：系统运转与渲染 ---
if st.button("🚀 启动三层漏斗扫描", type="primary"):
    with st.spinner("系统正在进行: 读取核心库 -> 腾讯基本面排雷 -> 量价筛选..."):
        
        # 1. 获取选定池子的股票代码
        target_codes = THEMES_DB[selected_theme]
        
        # 2. 批量请求腾讯接口获取全维度数据
        df = fetch_tencent_batch_data(target_codes)
        
        if not df.empty:
            # 3. 执行漏斗 2：基本面排雷
            initial_count = len(df)
            df = df[(df['市盈率(PE)'] > 0) & (df['市盈率(PE)'] <= max_pe)]
            if require_pb:
                df = df[(df['市净率(PB)'] > 0) & (df['市净率(PB)'] <= 2.0)]
            
            # 4. 执行漏斗 3：寻找极致
