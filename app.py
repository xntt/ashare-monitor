import streamlit as st
import pandas as pd
import requests
import re
import time

# ==========================================
# 0. 你的原版 8 个 + 要求的 3 个核心板块
# ==========================================
BASE_SECTORS = {
    # --- 你要求添加的 3 个 ---
    "📌【特加】稀土永磁": "chgn_700063",
    "📌【特加】化工行业": "new_bl_hghy",
    "📌【特加】有色金属": "new_bl_ysjs",
    # --- 你原来的 8 个 ---
    "【概念】低空经济": "chgn_700295",
    "【概念】机器人概念": "chgn_700251",
    "【概念】固态电池": "chgn_700249",
    "【概念】人工智能": "chgn_700116",
    "【概念】算力租赁": "chgn_700234",
    "【行业】半导体": "new_bl_bdt",
    "【行业】汽车行业": "new_bl_qchy",
    "【行业】医疗器械": "new_bl_ylqx"
}

def get_headers():
    # 最干爽的请求头，绝对不触发新浪任何拦截
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}

# ==========================================
# 1. 纯正则万能提取：新浪名单 + 腾讯行情
# ==========================================
# 【关键修复】：缓存时间缩短到 5 秒，彻底解决“空数据被卡住”的缓存BUG！
@st.cache_data(ttl=5)
def fetch_data_sina_tencent(node_code):
    if not node_code: return pd.DataFrame()
    
    # --- 第一步：新浪拿名单 ---
    sina_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "300", "sort": "symbol", "asc": "1", "node": node_code}
    
    try:
        s_res = requests.get(sina_url, params=params, headers=get_headers(), timeout=5)
        # 流氓提取法：不管新浪返回什么格式，只要里面有 sh/sz 开头的6位代码，全抓出来！
        symbols = re.findall(r'(sh\d{6}|sz\d{6})', s_res.text, re.IGNORECASE)
        symbols = list(dict.fromkeys([s.lower() for s in symbols])) # 去重
    except Exception:
        return pd.DataFrame()

    if not symbols: return pd.DataFrame()

    # --- 第二步：腾讯拿数据 ---
    clean_data = []
    chunk_size = 50 
    
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        t_url = f"http://qt.gtimg.cn/q={','.join(chunk)}"
        
        try:
            t_res = requests.get(t_url, headers=get_headers(), timeout=5)
            t_res.encoding = 'gbk' 
            lines = t_res.text.strip().split('\n')
            
            for line in lines:
                if "=" not in line: continue
                fields = line.split('=')[1].replace('"', '').split('~')
                if len(fields) < 47: continue 
                
                def to_float(val):
                    try: return float(val)
                    except: return 0.0

                clean_data.append({
                    "代码": fields[2],
                    "名称": fields[1],
                    "最新价": to_float(fields[3]),
                    "涨跌幅(%)": to_float(fields[32]),     
                    "换手率(%)": to_float(fields[38]),     
                    "市盈率(PE)": to_float(fields[39]),    
                    "市净率(PB)": to_float(fields[46]),    
                    "总市值(亿)": to_float(fields[45]),    
                })
            time.sleep(0.1) 
        except Exception:
            continue

    return pd.DataFrame(clean_data)

# ==========================================
# 2. 界面渲染
# ==========================================
st.set_page_config(page_title="完全透视版雷达", layout="wide")
st.markdown("### 🦅 极致稳定版：揭开新浪底层真实数据")

st.sidebar.header("🎯 1. 选择板块")
# 只显示你要求的 11 个板块，干干净净
selected_sector_name = st.sidebar.selectbox(
    "请选择：", 
    list(BASE_SECTORS.keys())
)

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 量化漏斗过滤")
st.sidebar.caption("⚠️ 注意：如果主界面没数据，请把这里调宽！")
max_pe = st.sidebar.slider("最大动态市盈率 (PE) [调到300看亏损股]", 0, 500, 100)
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)
min_turn = st.sidebar.number_input("最小换手率 (%) [调到0可看所有股]", value=2.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (-10.0, 11.0), step=0.5) # 默认放开涨跌幅！

node_code = BASE_SECTORS.get(selected_sector_name)
st.markdown(f"#### 正在监控：**{selected_sector_name}**")

with st.spinner("正在从新浪获取名单，从腾讯获取行情..."):
    df_stocks = fetch_data_sina_tencent(node_code)

if not df_stocks.empty:
    df_filtered = df_stocks.copy()
    # 执行过滤
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.success(f"✅ 底层透视：新浪一共成功返回了 **{len(df_stocks)}** 只成分股。经过左侧漏斗过滤后，剩余 **{len(df_filtered)}** 只！")
    
    if not df_filtered.empty:
        def color_change(val):
            return f"color: {'red' if val > 0 else 'green' if val < 0 else 'gray'}"
            
        styled_df = df_filtered.style.map(color_change, subset=['涨跌幅(%)'])\
                            .format({
                                "最新价": "{:.2f}", "涨跌幅(%)": "{:.2f}%", 
                                "换手率(%)": "{:.2f}%", "市盈率(PE)": "{:.2f}", 
                                "市净率(PB)": "{:.2f}", "总市值(亿)": "{:.2f}"
                            })
        st.dataframe(styled_df, use_container_width=True, height=400)
    else:
        st.warning("⚠️ 左侧的【换手率】或【市盈率】条件太苛刻了！该板块的票被漏斗全杀光了。你可以把换手率调成 0 试试。")
        
    with st.expander("🔍 不信你点开看：新浪传回的【全部原始数据】（无视漏斗）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.error("未能获取数据。可能是休市，或者网络波动，稍等几秒再试。")
