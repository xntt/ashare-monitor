import streamlit as st
import pandas as pd
import requests
import urllib.parse

# ==========================================
# 0. 东方财富内部精准板块代码 (BK Code)
# ==========================================
# 纯手工精准映射，免去去东方财富拉取“全市场板块”被封IP的风险
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
# 1. 强健的获取逻辑 (防云端IP被封锁 + 代理兜底)
# ==========================================
@st.cache_data(ttl=10) # 10秒短缓存
def fetch_eastmoney_data(bk_code):
    # 东方财富原生行情接口 (带有 fltt=2 解决小数问题)
    # 字段解析: f12:代码, f14:名称, f2:最新价, f3:涨跌幅, f8:换手率, f9:动态PE, f23:市净率, f20:总市值
    target_url = f"http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b:{bk_code}&fields=f12,f14,f2,f3,f8,f9,f23,f20"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://quote.eastmoney.com/"
    }

    raw_json = None
    
    # --- 策略1：极速直连尝试 (如果没被封锁则秒开) ---
    try:
        res = requests.get(target_url, headers=headers, timeout=3)
        if res.status_code == 200:
            raw_json = res.json()
    except Exception:
        pass

    # --- 策略2：Allorigins 代理兜底 (专门突破 Streamlit 云服务器 IP 被封) ---
    if not raw_json:
        try:
            # 将东方财富的接口打包扔给 allorigins 代理节点
            encoded_url = urllib.parse.quote(target_url)
            proxy_url = f"https://api.allorigins.win/raw?url={encoded_url}"
            res = requests.get(proxy_url, timeout=8)
            if res.status_code == 200:
                raw_json = res.json()
        except Exception:
            return pd.DataFrame() # 如果代理也挂了，返回空

    # 安全校验返回数据
    if not raw_json or "data" not in raw_json or raw_json["data"] is None:
        return pd.DataFrame()

    # 解析清洗数据
    stock_list = raw_json["data"].get("diff", [])
    clean_data = []
    
    for s in stock_list:
        # 东方财富对于停牌或者亏损的股票会返回 "-"
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
            # 原始市值是“元”，除以1亿变成“亿元”
            "总市值(亿)": to_float(s.get("f20")) / 100000000.0 if s.get("f20") and s.get("f20") != "-" else 0.0
        })
        
    return pd.DataFrame(clean_data)

# ==========================================
# 2. 页面与组件渲染
# ==========================================
st.set_page_config(page_title="东方财富底层直通版", layout="wide")
st.markdown("### 🦅 终极稳定版：直连东方财富 API + 智能代理突破")

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
with st.spinner("🚀 正在呼叫东方财富接口 (若遇云端拦截将自动切换代理)..."):
    df_stocks = fetch_eastmoney_data(bk_code)

if not df_stocks.empty:
    df_filtered = df_stocks.copy()
    
    # 漏斗执行
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    
    # 按换手降序
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.success(f"✅ 底层透视：东方财富该板块共包含 **{len(df_stocks)}** 只股票。漏斗过滤后幸存 **{len(df_filtered)}** 只！")
    
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
    st.error("❌ 数据获取失败。可能原因：网络严重波动、休市、或双重节点均被拦截。请几秒后再试。")
