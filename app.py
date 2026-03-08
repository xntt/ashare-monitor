import streamlit as st
import pandas as pd
import requests
import re
import json
import time

# ==========================================
# 备用防线：如果动态扫描意外失败，启用此备用库保证系统不瘫痪
# ==========================================
FALLBACK_SECTORS = {
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
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}

# ==========================================
# 1. 动态板块扫描 (修复了极其脆弱的解析逻辑)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_sectors_safely():
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    sectors = {}
    try:
        res = requests.get(url, headers=get_headers(), timeout=5)
        text = res.text
        
        # 终极暴力正则：直接从长字符串中硬抠“中文名”和“对应代码”，无视任何 JSON 格式错误
        # 概念代码特征：chgn_开头； 行业代码特征：new_bl_开头
        matches = re.findall(r'["\']?([^"\',:{}\[\]]+)["\']?\s*[,:]\s*["\']?(chgn_\d+|new_bl_[a-zA-Z0-9]+)["\']?', text)
        
        for name, code in matches:
            # 清洗名字中的无效字符
            name = name.replace("name", "").replace("\"", "").strip()
            if len(name) > 1 and len(name) < 10: # 只保留正常的中文名
                prefix = "【概念】" if code.startswith("chgn_") else "【行业】"
                sectors[f"{prefix}{name}"] = code
                
        if len(sectors) > 50:
            return sectors, "📡 成功实时扫描全市场动态板块"
        else:
            return FALLBACK_SECTORS, "⚠️ 扫描结果过少，已启用系统内置热门板块库"
    except Exception as e:
        return FALLBACK_SECTORS, f"⚠️ 网络异常，已启用系统内置板块库 ({e})"

# ==========================================
# 2. 新浪拿名单 + 腾讯拿数据 (加入你说的访问限频)
# ==========================================
@st.cache_data(ttl=60)
def fetch_data_sina_tencent(node_code):
    if not node_code: return pd.DataFrame()
    
    # --- 第一步：新浪拿名单 ---
    sina_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "300", "sort": "symbol", "asc": "1", "node": node_code}
    
    try:
        s_res = requests.get(sina_url, params=params, headers=get_headers(), timeout=5)
        # 修复新浪残缺JSON的经典方法
        fixed_text = re.sub(r'([{,])\s*([a-zA-Z_]\w*)\s*:', r'\1"\2":', s_res.text)
        sina_data = json.loads(fixed_text)
        symbols = [item['symbol'] for item in sina_data if 'symbol' in item]
    except Exception as e:
        st.error("获取板块成分股名单失败。")
        return pd.DataFrame()

    if not symbols: return pd.DataFrame()

    # --- 第二步：腾讯拿数据 (加入限频 time.sleep) ---
    clean_data = []
    chunk_size = 50 # 每次只向腾讯查 50 个，避免 URL 过长被拦截
    
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
            # 【核心修复】控制访问频率，每次请求腾讯后停顿 0.1 秒
            time.sleep(0.1) 
        except Exception:
            continue

    return pd.DataFrame(clean_data)

# ==========================================
# 3. Streamlit 界面
# ==========================================
st.set_page_config(page_title="回归稳定版雷达", layout="wide")
st.markdown("### 🦅 稳定双擎版：新浪目录 + 腾讯行情 (带防崩溃机制)")

# 获取动态板块
dynamic_sectors, status_msg = fetch_sectors_safely()
st.caption(status_msg) # 在标题下方显示当前扫描状态

# 侧边栏设置
st.sidebar.header("🎯 1. 搜索与选择板块")
# selectbox自带全拼音/中文搜索功能
selected_sector_name = st.sidebar.selectbox(
    "输入关键词搜索 (例如: 算力 / 低空)：", 
    list(dynamic_sectors.keys())
)

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 量化漏斗")
max_pe = st.sidebar.slider("最大动态市盈率 (PE)", 0, 300, 100)
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)
min_turn = st.sidebar.number_input("最小换手率 (%)", value=2.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 5.0), step=0.5)

node_code = dynamic_sectors.get(selected_sector_name)
st.markdown(f"#### 正在监控：**{selected_sector_name}**")

# 拉取与过滤数据
with st.spinner(f"正在读取 {selected_sector_name} 实时数据... (已开启限频保护)"):
    df_stocks = fetch_data_sina_tencent(node_code)

if not df_stocks.empty:
    df_filtered = df_stocks.copy()
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.markdown(f"📦 板块共 **{len(df_stocks)}** 只成分股。漏斗过滤后剩余 **{len(df_filtered)}** 只！")
    
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
        st.warning("⚠️ 条件太苛刻啦，该板块内的股票全军覆没。")
        
    with st.expander("🔍 点击查看全部底层原始数据（未过滤）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.error("未能获取到数据，可能是休市或该板块数据为空。")
