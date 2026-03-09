import streamlit as st
import pandas as pd
import requests
import re
import time

# ==========================================
# 0. 强制置顶区：你要求的核心板块 (永远在下拉框最前面)
# ==========================================
CUSTOM_SECTORS = {
    "📌【特加】稀土永磁": "chgn_700063",
    "📌【特加】化工行业": "new_bl_hghy",
    "📌【特加】有色金属": "new_bl_ysjs",
    "📌【特加】算力租赁": "chgn_700234",
    "📌【特加】低空经济": "chgn_700295"
}

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
        "Referer": "http://finance.sina.com.cn/"
    }

# ==========================================
# 1. 获取全市场板块目录 (彻底修复：置顶 + 300动态全量)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_sectors_safely():
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    # 第一步：把置顶板块放进字典
    sectors = CUSTOM_SECTORS.copy() 
    
    try:
        res = requests.get(url, headers=get_headers(), timeout=5)
        res.encoding = 'gbk' # 强制处理新浪的中文字符，防止正则失效
        
        # 第二步：暴力扫描新浪全部 300+ 个动态板块
        matches = re.findall(r'"([^"]+)"\s*,\s*"(chgn_\d+|new_bl_[a-zA-Z0-9_]+)"', res.text)
        
        count = 0
        for name, code in matches:
            if "板块" in name or "指数" in name: continue # 过滤掉没用的父节点
            prefix = "【概念】" if code.startswith("chgn_") else "【行业】"
            key = f"{prefix}{name}"
            
            # 只要不是重复的，就统统加进字典的后面
            if key not in sectors:
                sectors[key] = code
                count += 1
                
        return sectors, f"📡 成功加载 {len(sectors)} 个板块目录 (含置顶 {len(CUSTOM_SECTORS)} 个，动态抓取 {count} 个)"
    except Exception as e:
        return sectors, f"⚠️ 动态扫描因网络波动受限，当前仅展示核心置顶目录"

# ==========================================
# 2. 纯正则提取名单 + 腾讯限频拿数据 (彻底解决JSON崩溃不出数据)
# ==========================================
@st.cache_data(ttl=60)
def fetch_data_sina_tencent(node_code):
    if not node_code: return pd.DataFrame()
    
    # --- 第一步：新浪拿名单 (纯正则穿透) ---
    sina_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "300", "sort": "symbol", "asc": "1", "node": node_code}
    
    try:
        s_res = requests.get(sina_url, params=params, headers=get_headers(), timeout=5)
        # 【关键一击】：抛弃 json.loads，像剪刀一样直接从乱码里抠出所有股票代码！
        symbols = re.findall(r'symbol\s*:\s*["\']?(s[hz]\d{6})["\']?', s_res.text)
        symbols = list(dict.fromkeys(symbols)) # 列表去重
    except Exception as e:
        st.error("获取板块成分股名单失败")
        return pd.DataFrame()

    if not symbols: return pd.DataFrame()

    # --- 第二步：腾讯极速拿数据 (含限频保护) ---
    clean_data = []
    chunk_size = 50 # 每批只查50个，防止被封
    
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
                if len(fields) < 47: continue # 过滤停牌或退市股
                
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
            # 【核心限频】：每次查完强制歇 0.1 秒，保证后续请求畅通无阻
            time.sleep(0.1) 
        except Exception:
            continue

    return pd.DataFrame(clean_data)

# ==========================================
# 3. Streamlit UI 渲染界面
# ==========================================
st.set_page_config(page_title="完全体雷达", layout="wide")
st.markdown("### 🦅 极致稳定版：全量目录 + 特加板块 + 纯正则解析")

# 调用板块扫描器
dynamic_sectors, status_msg = fetch_sectors_safely()
st.caption(status_msg)

# 左侧控制台
st.sidebar.header("🎯 1. 搜索与选择板块")
selected_sector_name = st.sidebar.selectbox(
    "下拉选择或输入汉字拼音搜索：", 
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

# 拉取核心数据
with st.spinner(f"正在读取 {selected_sector_name} 实时数据... (正则穿透模式)"):
    df_stocks = fetch_data_sina_tencent(node_code)

if not df_stocks.empty:
    df_filtered = df_stocks.copy()
    # 漏斗清洗
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
    st.error("未能获取到数据。可能是休市或该板块内暂无个股数据。")
