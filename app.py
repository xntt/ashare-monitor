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
# 1. 终极穿透引擎 (备用节点轮询 + 代理高延迟容忍)
# ==========================================
@st.cache_data(ttl=15)
def fetch_eastmoney_data(bk_code):
    # 黑科技1：东方财富边缘节点大轮盘，避开主服务器的严厉封锁
    subdomains = ["push2", "8.push2", "11.push2", "90.push2", "78.push2", "5.push2"]
    sub = random.choice(subdomains)
    
    # 黑科技2：强制使用 https 加密协议
    target_url = f"https://{sub}.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b:{bk_code}&fields=f12,f14,f2,f3,f8,f9,f23,f20"
    
    # 随机 User-Agent 防止被指纹识别
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://quote.eastmoney.com/"
    }

    debug_log = []
    
    def try_parse(response):
        """安全解析JSON，防止代理返回死网页导致崩溃"""
        try:
            return response.json()
        except Exception:
            return None

    # --- 策略1：加密直连边缘节点 ---
    try:
        res = requests.get(target_url, headers=headers, timeout=5)
        if res.status_code == 200:
            raw_json = try_parse(res)
            if raw_json and raw_json.get("data"): 
                return parse_json_to_df(raw_json), f"直连穿透 ({sub}节点)"
            else:
                debug_log.append(f"直连[{sub}]: 被拦截返回非数据内容")
    except Exception as e:
        debug_log.append(f"直连失败: {str(e)[:50]}")

    encoded_url = urllib.parse.quote(target_url)

    # --- 策略2：Allorigins 超长续航 (解决 Read timed out 痛点) ---
    try:
        proxy_url = f"https://api.allorigins.win/raw?url={encoded_url}"
        # 核心：将超时从 6 秒拉大到 15 秒！等它！
        res = requests.get(proxy_url, timeout=15)
        if res.status_code == 200:
            raw_json = try_parse(res)
            if raw_json and raw_json.get("data"): 
                return parse_json_to_df(raw_json), "AllOrigins(15秒高延迟兜底)"
            else:
                debug_log.append("Allorigins: 返回了错误的数据格式")
    except Exception as e:
        debug_log.append(f"Allorigins失败: {str(e)[:50]}")

    # --- 策略3：Thingproxy 备用通道 ---
    try:
        proxy_url = f"https://thingproxy.freeboard.io/fetch/{target_url}"
        res = requests.get(proxy_url, timeout=10)
        if res.status_code == 200:
            raw_json = try_parse(res)
            if raw_json and raw_json.get("data"): 
                return parse_json_to_df(raw_json), "ThingProxy通道"
            else:
                debug_log.append("ThingProxy: 格式错误或被阻挡")
    except Exception as e:
        debug_log.append(f"ThingProxy失败: {str(e)[:50]}")

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
st.markdown("### 🦅 游资雷达：东方财富直连防断版")

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
with st.spinner("🚀 正在强行穿透东方财富服务器 (最长可能等待15秒，请耐心)..."):
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
    st.error("❌ 破防失败！15秒超时内未能穿透。")
    st.error("👇 错误诊断日志：")
    for log in debug_info:
        st.code(log)
