import streamlit as st
import pandas as pd
import requests
import re
import time

# ==========================================
# 0. 基础保障库：你原来的 8 个 + 新增的 3 个，全都在这！
# ==========================================
BASE_SECTORS = {
    # --- 新增的3个 ---
    "📌【特加】稀土永磁": "chgn_700063",
    "📌【特加】化工行业": "new_bl_hghy",
    "📌【特加】有色金属": "new_bl_ysjs",
    # --- 你原来的8个 ---
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
    # 删除了触发拦截的 Referer，回归最干净的请求头
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}

# ==========================================
# 1. 获取全市场板块目录 (优先显示你的，再追加全网的)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_sectors_safely():
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    sectors = BASE_SECTORS.copy() 
    
    try:
        res = requests.get(url, headers=get_headers(), timeout=5)
        # 提取动态板块
        matches = re.findall(r'"([^"]+)"\s*,\s*"(chgn_\d+|new_bl_[a-zA-Z0-9_]+)"', res.text)
        
        for name, code in matches:
            if "板块" in name or "指数" in name: continue 
            prefix = "【概念】" if code.startswith("chgn_") else "【行业】"
            key = f"{prefix}{name}"
            # 追加不重复的板块
            if key not in sectors:
                sectors[key] = code
                
        return sectors, f"📡 成功加载 {len(sectors)} 个板块目录"
    except Exception as e:
        return sectors, f"⚠️ 仅加载了基础板块（网络动态抓取受限）"

# ==========================================
# 2. 纯代码提取 + 腾讯行情抓取 (无视JSON报错)
# ==========================================
@st.cache_data(ttl=60)
def fetch_data_sina_tencent(node_code):
    if not node_code: return pd.DataFrame()
    
    # --- 第一步：新浪拿名单 ---
    sina_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "300", "sort": "symbol", "asc": "1", "node": node_code}
    
    try:
        s_res = requests.get(sina_url, params=params, headers=get_headers(), timeout=5)
        
        # 【终极提取大法】：不管返回的是啥乱码，直接全局搜索 shXXXXXX 和 szXXXXXX 
        # IGNORECASE 用来防止新浪偶尔返回大写的 SH 导致漏掉
        symbols = re.findall(r'(sh\d{6}|sz\d{6})', s_res.text, re.IGNORECASE)
        
        # 转成小写并且去重
        symbols = list(dict.fromkeys([s.lower() for s in symbols])) 
    except Exception:
        st.error("获取板块成分股名单失败")
        return pd.DataFrame()

    if not symbols: return pd.DataFrame()

    # --- 第二步：腾讯拿数据 (带限频防封) ---
    clean_data = []
    chunk_size = 50 
    
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        t_url = f"http://qt.gtimg.cn/q={','.join(chunk)}"
        
        try:
            t_res = requests.get(t_url, headers=get_headers(), timeout=5)
            t_res.encoding = 'gbk' # 腾讯接口必须用 gbk 解析
            lines = t_res.text.strip().split('\n')
            
            for line in lines:
                if "=" not in line: continue
                fields = line.split('=')[1].replace('"', '').split('~')
                if len(fields) < 47: continue # 过滤停牌或无数据的
                
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
            # 【限频保护】每次查完 50 个歇 0.1 秒
            time.sleep(0.1) 
        except Exception:
            continue

    return pd.DataFrame(clean_data)

# ==========================================
# 3. 界面渲染
# ==========================================
st.set_page_config(page_title="稳定不崩版雷达", layout="wide")
st.markdown("### 🦅 极致稳定版：全量目录 + 万能提取")

dynamic_sectors, status_msg = fetch_sectors_safely()
st.caption(status_msg)

st.sidebar.header("🎯 1. 选择板块")
# 你要的11个板块肯定都在下拉框最前面
selected_sector_name = st.sidebar.selectbox(
    "下拉选择或输入关键词搜索：", 
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

with st.spinner(f"正在抓取 {selected_sector_name} 数据..."):
    df_stocks = fetch_data_sina_tencent(node_code)

if not df_stocks.empty:
    df_filtered = df_stocks.copy()
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.markdown(f"📦 共查到 **{len(df_stocks)}** 只股票。漏斗过滤后剩余 **{len(df_filtered)}** 只！")
    
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
        st.warning("⚠️ 漏斗条件太苛刻了，这板块的股票都被筛掉了。")
        
    with st.expander("🔍 点击查看：板块全部原始数据（未过滤）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.error("未能获取数据。可能是休市，或者你点太快被限制了，稍等5秒再试。")
