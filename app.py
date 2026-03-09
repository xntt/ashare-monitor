import streamlit as st
import pandas as pd
import requests
import re
import time

# ==========================================
# 0. 强制置顶：你要求添加的核心板块
# ==========================================
CUSTOM_SECTORS = {
    "📌【特加】稀土永磁": "chgn_700063",
    "📌【特加】化工行业": "new_bl_hghy",
    "📌【特加】有色金属": "new_bl_ysjs",
    "📌【特加】算力租赁": "chgn_700234",
    "📌【特加】低空经济": "chgn_700295"
}

def get_headers():
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}

# ==========================================
# 1. 获取全市场板块目录 (优化了解析逻辑)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_sectors_safely():
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    sectors = CUSTOM_SECTORS.copy() # 把你要求的板块强行放在最前面
    
    try:
        res = requests.get(url, headers=get_headers(), timeout=5)
        # 精准匹配新浪目录格式：提取板块名和对应的代码
        matches = re.findall(r'"([^"]+)"\s*,\s*"(chgn_\d+|new_bl_[a-z_]+)"', res.text)
        
        for name, code in matches:
            if name in ["概念板块", "行业板块", "地域板块"]: continue
            prefix = "【概念】" if code.startswith("chgn_") else "【行业】"
            sectors[f"{prefix}{name}"] = code
            
        return sectors, f"📡 成功加载 {len(sectors)} 个板块目录"
    except Exception as e:
        return sectors, f"⚠️ 网络原因未获取全部目录，已加载核心基础目录"

# ==========================================
# 2. 核心修复：纯正则提取名单 + 腾讯限频获取数据
# ==========================================
@st.cache_data(ttl=60)
def fetch_data_sina_tencent(node_code):
    if not node_code: return pd.DataFrame()
    
    # --- 第一步：新浪拿名单 ---
    sina_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "300", "sort": "symbol", "asc": "1", "node": node_code}
    
    try:
        s_res = requests.get(sina_url, params=params, headers=get_headers(), timeout=5)
        
        # 【根本性修复】彻底抛弃脆弱的 json.loads！
        # 像激光一样，直接从乱码中抠出所有的 shXXXXXX 和 szXXXXXX 股票代码
        symbols = re.findall(r'symbol\s*:\s*["\']?(s[hz]\d{6})["\']?', s_res.text)
        
        # 去重，防止新浪返回重复数据
        symbols = list(dict.fromkeys(symbols)) 
    except Exception as e:
        st.error("获取板块成分股名单失败")
        return pd.DataFrame()

    if not symbols: return pd.DataFrame()

    # --- 第二步：腾讯拿数据 (带限频保护) ---
    clean_data = []
    chunk_size = 50 # 每次只发 50 个代码，防止 URL 超载
    
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
                if len(fields) < 47: continue # 过滤停牌或退市
                
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
            # 【限频保护】每次向腾讯请求后强制休息 0.1 秒
            time.sleep(0.1) 
        except Exception:
            continue

    return pd.DataFrame(clean_data)

# ==========================================
# 3. Streamlit UI 渲染
# ==========================================
st.set_page_config(page_title="最强解封版雷达", layout="wide")
st.markdown("### 🦅 极致稳定版：新浪名单 + 腾讯行情 (纯正则提取版)")

dynamic_sectors, status_msg = fetch_sectors_safely()
st.caption(status_msg)

st.sidebar.header("🎯 1. 搜索与选择板块")
selected_sector_name = st.sidebar.selectbox(
    "输入关键词搜索 (例如: 稀土 / 化工 / 有色)：", 
    list(dynamic_sectors.keys())
)

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 量化漏斗过滤")
max_pe = st.sidebar.slider("最大动态市盈率 (PE)", 0, 300, 100)
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)
min_turn = st.sidebar.number_input("最小换手率 (%)", value=2.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 5.0), step=0.5)

node_code = dynamic_sectors.get(selected_sector_name)
st.markdown(f"#### 正在监控：**{selected_sector_name}**")

with st.spinner(f"正在读取 {selected_sector_name} 实时数据... (已开启正则穿透)"):
    df_stocks = fetch_data_sina_tencent(node_code)

if not df_stocks.empty:
    df_filtered = df_stocks.copy()
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.markdown(f"📦 该板块共有 **{len(df_stocks)}** 只成分股。量化漏斗过滤后剩余 **{len(df_filtered)}** 只！")
    
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
        st.warning("⚠️ 条件太苛刻，该板块内的股票已被漏斗全部拦截。")
        
    with st.expander("🔍 点击查看：腾讯接口返回的全部底层数据（未过滤）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.error("未能获取到数据。可能是休市或该板块内无数据。")
