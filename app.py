import streamlit as st
import pandas as pd
import requests
import urllib.parse
import random

# ==========================================
# 0. 东方财富内部精准板块代码 (BK Code)
# ==========================================
BASE_SECTORS = {
    "📌【特加】稀土永磁": "BK0578",
    "📌【特加】化工行业(化学制品)": "BK0465", 
    "📌【特加】有色金属": "BK0478",
    "【概念】低空经济": "BK1166",
    "【概念】机器人概念": "BK1090",
    "【概念】固态电池": "BK0968",
    "【概念】人工智能": "BK0800",
    "【概念】算力租赁": "BK1134",
    "【行业】半导体": "BK1036",
    "【行业】汽车整车": "BK1029",
    "【行业】医疗器械": "BK1041"
}

# ==========================================
# 1. 终极反爬虫网络引擎 (IP伪装 + 3重代理轮换)
# ==========================================
@st.cache_data(ttl=15)
def fetch_eastmoney_data(bk_code):
    target_url = f"http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b:{bk_code}&fields=f12,f14,f2,f3,f8,f9,f23,f20"
    
    # 核心黑科技：每次请求随机生成一个国内的虚拟 IP 地址，欺骗东方财富 WAF 防火墙
    fake_ip = f"{random.randint(114, 115)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://quote.eastmoney.com/",
        "X-Forwarded-For": fake_ip,  # 伪装 IP
        "X-Real-IP": fake_ip         # 伪装 IP
    }

    # 用于记录失败原因，方便排错
    debug_log = []
    raw_json = None

    # --- 策略1：注入虚拟IP直连 ---
    try:
        res = requests.get(target_url, headers=headers, timeout=4)
        if res.status_code == 200:
            raw_json = res.json()
            if raw_json.get("data"): 
                return parse_json_to_df(raw_json), "直连+IP伪装"
            else:
                debug_log.append("直连成功但被东方财富拦截(返回空data)")
                raw_json = None
    except Exception as e:
        debug_log.append(f"直连失败: {str(e)}")

    encoded_url = urllib.parse.quote(target_url)

    # --- 策略2：Corsproxy 代理兜底 ---
    if not raw_json:
        try:
            proxy_url = f"https://corsproxy.io/?{encoded_url}"
            res = requests.get(proxy_url, timeout=6)
            if res.status_code == 200:
                raw_json = res.json()
                if raw_json.get("data"): return parse_json_to_df(raw_json), "Corsproxy代理"
        except Exception as e:
            debug_log.append(f"Corsproxy失败: {str(e)}")

    # --- 策略3：Codetabs 代理兜底 ---
    if not raw_json:
        try:
            proxy_url = f"https://api.codetabs.com/v1/proxy?quest={target_url}"
            res = requests.get(proxy_url, timeout=6)
            if res.status_code == 200:
                raw_json = res.json()
                if raw_json.get("data"): return parse_json_to_df(raw_json), "Codetabs代理"
        except Exception as e:
            debug_log.append(f"Codetabs失败: {str(e)}")

    # --- 策略4：Allorigins 代理兜底 ---
    if not raw_json:
        try:
            proxy_url = f"https://api.allorigins.win/raw?url={encoded_url}"
            res = requests.get(proxy_url, timeout=6)
            if res.status_code == 200:
                raw_json = res.json()
                if raw_json.get("data"): return parse_json_to_df(raw_json), "AllOrigins代理"
        except Exception as e:
            debug_log.append(f"Allorigins失败: {str(e)}")

    # 如果全军覆没，返回错误日志
    return pd.DataFrame(), debug_log

def parse_json_to_df(raw_json):
    stock_list = raw_json.get("data", {}).get("diff", [])
    clean_data = []
    for s in stock_list:
        def to_float(val):
            try: return float(val) if val != "-" else 0.0
            except: return 0.0

        clean_data.append({
            "代码": str(s.get("f12", "")),
            "名称": str(s.get("f14", "")),
            "最新价": to_float(s.get("f2")),
            "涨跌幅(%)": to_float(s.get("f3")),
            "换手率(%)": to_float(s.get("f8")),
            "市盈率(PE)": to_float(s.get("f9")),
            "市净率(PB)": to_float(s.get("f23")),
            "总市值(亿)": to_float(s.get("f20")) / 100000000.0 if s.get("f20") and s.get("f20") != "-" else 0.0
        })
    return pd.DataFrame(clean_data)

# ==========================================
# 2. 页面与组件渲染
# ==========================================
st.set_page_config(page_title="游资板块透视", layout="wide")
st.markdown("### 🦅 终极反侦察版：多重代理 + IP伪装防拦截")

st.sidebar.header("🎯 1. 选择板块")
selected_sector = st.sidebar.selectbox("请选择要扫描的板块：", list(BASE_SECTORS.keys()))

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 量化漏斗过滤")
st.sidebar.caption("提示：主界面无数据时，把换手率调到0即可看到所有股")
max_pe = st.sidebar.slider("最大动态市盈率 (PE)", 0, 500, 100)
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)
min_turn = st.sidebar.number_input("最小换手率 (%) [填0看全部]", value=2.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (-10.0, 11.0), step=0.5)

bk_code = BASE_SECTORS[selected_sector]
st.markdown(f"#### 正在监控：**{selected_sector}** (内部代码: {bk_code})")

# 加载数据
with st.spinner("🚀 正在注入虚拟IP，尝试突破东方财富封锁..."):
    result, debug_info = fetch_eastmoney_data(bk_code)

if not result.empty:
    df_stocks = result
    st.success(f"✅ 数据拉取成功！当前使用通道: **{debug_info}**")
    
    df_filtered = df_stocks.copy()
    
    # 漏斗执行
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    
    # 按换手降序
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.info(f"📊 该板块共包含 **{len(df_stocks)}** 只股票。漏斗过滤后幸存 **{len(df_filtered)}** 只！")
    
    if not df_filtered.empty:
        def color_change(val):
            return f"color: {'red' if val > 0 else 'green' if val < 0 else 'gray'}"
            
        styled_df = df_filtered.style.map(color_change, subset=['涨跌幅(%)'])\
                            .format({
                                "最新价": "{:.2f}", "涨跌幅(%)": "{:.2f}%", 
                                "换手率(%)": "{:.2f}%", "市盈率(PE)": "{:.2f}", 
                                "市净率(PB)": "{:.2f}", "总市值(亿)": "{:.2f}"
                            })
        st.dataframe(styled_df, use_container_width=True, height=450)
    else:
        st.warning("⚠️ 漏斗条件太苛刻！你把左侧的【最小换手率】改成 0 看看。")
        
    with st.expander("🔍 展开查看：东方财富返回的【全量原始数据】（无视漏斗）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.error("❌ 严重错误：突破东方财富失败！所有通道均被拦截！")
    st.error("👇 错误诊断日志（如果还失败，请把这段日志截图给我看）：")
    for log in debug_info:
        st.code(log)
