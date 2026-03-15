import streamlit as st
import pandas as pd
import requests
import urllib.request
import urllib.parse
import json
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
# 1. 降维打击网络引擎 (HTTP降级 + Urllib原生穿透)
# ==========================================
@st.cache_data(ttl=15)
def fetch_eastmoney_data(bk_code):
    # 核心修改1：去掉了 HTTPS，恢复纯 HTTP 协议，迎合东方财富老旧服务器
    # 核心修改2：准备了多个备用节点服务器
    endpoints = [
        "http://push2.eastmoney.com/api/qt/clist/get",
        "http://82.push2.eastmoney.com/api/qt/clist/get",
        "http://push2n.eastmoney.com/api/qt/clist/get"
    ]
    
    params = f"pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b:{bk_code}&fields=f12,f14,f2,f3,f8,f9,f23,f20"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "http://quote.eastmoney.com/",
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive"
    }

    debug_log = []

    # --- 策略1：使用 Python 原生 Urllib 库直连 (无视 requests 防火墙) ---
    for base_url in endpoints:
        full_url = f"{base_url}?{params}"
        try:
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                raw_data = response.read().decode('utf-8')
                json_data = json.loads(raw_data)
                if json_data and json_data.get("data"):
                    return parse_json_to_df(json_data), f"原生 Urllib 成功 ({base_url.split('/')[2]})"
                else:
                    debug_log.append(f"Urllib [{base_url.split('/')[2]}]: 返回空")
        except Exception as e:
            debug_log.append(f"Urllib [{base_url.split('/')[2]}] 失败: {str(e)[:40]}")

    # --- 策略2：使用常规 Requests 库直连 ---
    for base_url in endpoints:
        full_url = f"{base_url}?{params}"
        try:
            res = requests.get(full_url, headers=headers, timeout=4)
            if res.status_code == 200:
                json_data = res.json()
                if json_data and json_data.get("data"):
                    return parse_json_to_df(json_data), f"Requests 成功 ({base_url.split('/')[2]})"
        except Exception as e:
            debug_log.append(f"Requests [{base_url.split('/')[2]}] 失败: {str(e)[:40]}")

    # --- 策略3：AllOrigins 包装代理 (避免 Raw 超时) ---
    try:
        # 这次不用 raw，而是用 get 将数据包装成 JSON，解决上次 Read timed out 的问题
        proxy_url = f"https://api.allorigins.win/get?url={urllib.parse.quote(endpoints[0] + '?' + params)}"
        res = requests.get(proxy_url, timeout=12)
        if res.status_code == 200:
            wrapper = res.json()
            if "contents" in wrapper:
                json_data = json.loads(wrapper["contents"])
                if json_data and json_data.get("data"):
                    return parse_json_to_df(json_data), "AllOrigins (JSON包装模式)"
    except Exception as e:
        debug_log.append(f"AllOrigins 包装模式失败: {str(e)[:40]}")

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
st.markdown("### 🦅 游资雷达：原生 HTTP 降维打击版")

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
with st.spinner("🚀 正在使用纯净 HTTP 协议请求数据 (预计2~5秒)..."):
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
    st.error("❌ 拉取失败！")
    st.error("👇 错误诊断日志：")
    for log in debug_info:
        st.code(log)
