import streamlit as st
import pandas as pd
import requests
import re
import json
import random

# ==========================================
# 核心装甲：随机浏览器伪装头 (突破防爬虫屏蔽)
# ==========================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "http://finance.sina.com.cn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

# ==========================================
# 1. 新浪负责：全自动动态扫描“所有板块目录”
# ==========================================
@st.cache_data(ttl=3600)
def fetch_dynamic_sectors():
    """伪装成浏览器，抓取新浪的全市场动态板块字典"""
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    sector_dict = {}
    try:
        # 加入防屏蔽 Headers
        res = requests.get(url, headers=get_headers(), timeout=8)
        text = res.text
        
        # 提取概念板块
        for part in text.split('chgn_')[1:]:
            code_match = re.match(r'^(\d+)', part)
            name_match = re.search(r'name(?:["\']|\s|:)*["\']([^"\']+)["\']', part)
            if code_match and name_match:
                sector_dict[f"【概念】{name_match.group(1)}"] = f"chgn_{code_match.group(1)}"
                
        # 提取行业板块
        for part in text.split('new_bl_')[1:]:
            code_match = re.match(r'^(\d+)', part)
            name_match = re.search(r'name(?:["\']|\s|:)*["\']([^"\']+)["\']', part)
            if code_match and name_match:
                sector_dict[f"【行业】{name_match.group(1)}"] = f"new_bl_{code_match.group(1)}"
                
        return dict(sorted(sector_dict.items()))
    except Exception as e:
        st.error(f"板块获取被阻挡，请重试: {e}")
        return {}

# ==========================================
# 2. 核心协作：新浪给代码 -> 腾讯给基本面数据！
# ==========================================
@st.cache_data(ttl=60)
def fetch_tencent_data_for_sector(node_code):
    """
    第一步：找新浪要这个板块里所有股票的代码（sh600519, sz000001）
    第二步：拿着代码去找腾讯财经，批量拉取极速量价和基本面
    """
    if not node_code: return pd.DataFrame()
    
    # --- Step 1: 找新浪拿纯代码名单 ---
    sina_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {"page": "1", "num": "200", "sort": "symbol", "asc": "1", "node": node_code}
    
    try:
        res = requests.get(sina_url, params=params, headers=get_headers(), timeout=5)
        text = re.sub(r'(?<=[{,])([a-zA-Z_]\w*)(?=:)', r'"\1"', res.text) # 修复破损JSON
        sina_data = json.loads(text)
        
        # 提取股票代码列表，例如 ['sh600000', 'sz000001', ...]
        symbol_list = [stock.get('symbol') for stock in sina_data if stock.get('symbol')]
    except Exception as e:
        st.error("获取板块成分股名单失败（新浪端被拦截）")
        return pd.DataFrame()

    if not symbol_list:
        return pd.DataFrame()

    # --- Step 2: 找腾讯财经拿全部详细数据 (批量查询极速防封) ---
    # 将代码列表拼接成腾讯需要的格式，每次最多查 100 个防止 URL 过长
    tencent_url = f"http://qt.gtimg.cn/q={','.join(symbol_list[:100])}"
    
    try:
        t_res = requests.get(tencent_url, headers=get_headers(), timeout=5)
        t_res.encoding = 'gbk' # 腾讯接口是 GBK 编码
        
        # 腾讯返回的数据是以 \n 分隔的字符串
        lines = t_res.text.strip().split('\n')
        
        clean_data = []
        for line in lines:
            if not line or "=" not in line: continue
            
            # 解析腾讯格式：v_sh600519="1~贵州茅台~600519~1700.00~..."
            data_str = line.split('=')[1].replace('"', '')
            fields = data_str.split('~')
            
            if len(fields) < 47: continue # 过滤停牌或退市股票
            
            def to_float(val):
                try: return float(val)
                except: return 0.0

            # 腾讯财经字段映射解析 (核心硬核解析)
            clean_data.append({
                "代码": fields[2],
                "名称": fields[1],
                "最新价": to_float(fields[3]),
                "涨跌幅(%)": to_float(fields[32]),     # 腾讯字段32: 涨跌幅%
                "换手率(%)": to_float(fields[38]),     # 腾讯字段38: 换手率%
                "市盈率(PE)": to_float(fields[39]),    # 腾讯字段39: 动态市盈率
                "市净率(PB)": to_float(fields[46]),    # 腾讯字段46: 市净率
                "总市值(亿)": to_float(fields[45]),    # 腾讯字段45: 总市值(亿)
            })
            
        return pd.DataFrame(clean_data)
    except Exception as e:
        st.error(f"解析腾讯财经数据失败: {e}")
        return pd.DataFrame()

# ==========================================
# 3. 页面渲染与过滤漏斗
# ==========================================
st.set_page_config(page_title="V6.0 腾讯+新浪 双擎雷达", layout="wide")
st.markdown("### 🦅 V6.0 动态板块雷达 (腾讯财经极速版+反爬装甲)")

with st.spinner("📡 正在穿透防火墙，获取最新板块目录..."):
    dynamic_sectors = fetch_dynamic_sectors()

if dynamic_sectors:
    st.sidebar.header("🎯 第一步：搜索/选择动态板块")
    selected_sector_name = st.sidebar.selectbox(
        "输入关键词或下拉选择 (例如: 算力 / 低空经济)：", 
        list(dynamic_sectors.keys())
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 第二步：腾讯基本面过滤")
    max_pe = st.sidebar.slider("最大市盈率 (PE)", 0, 300, 80, help="腾讯实时PE，0表示过滤亏损")
    max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)

    st.sidebar.markdown("**游资量价买点**")
    min_turn = st.sidebar.number_input("最小换手率 (%)", value=2.0, step=0.5)
    price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 5.0), step=0.5)

    node_code = dynamic_sectors.get(selected_sector_name)
    st.markdown(f"#### 正在监控：**{selected_sector_name}**")
    
    with st.spinner(f"正在向腾讯财经批量请求 {selected_sector_name} 实时数据..."):
        df_stocks = fetch_tencent_data_for_sector(node_code)

    if not df_stocks.empty:
        # --- 内存漏斗清洗 ---
        df_filtered = df_stocks.copy()
        df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
        df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
        df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
        df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
        df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
        
        st.markdown(f"📦 腾讯接口返回 **{len(df_stocks)}** 只股票。漏斗清洗截获 **{len(df_filtered)}** 只标的！")
        
        if not df_filtered.empty:
            def color_change(val):
                color = 'red' if val > 0 else 'green' if val < 0 else 'gray'
                return f'color: {color}'
                
            styled_df = df_filtered.style.map(color_change, subset=['涨跌幅(%)'])\
                                .format({
                                    "最新价": "{:.2f}", 
                                    "涨跌幅(%)": "{:.2f}%", 
                                    "换手率(%)": "{:.2f}%", 
                                    "市盈率(PE)": "{:.2f}", 
                                    "市净率(PB)": "{:.2f}",
                                    "总市值(亿)": "{:.2f}"
                                })
            st.dataframe(styled_df, use_container_width=True, height=400)
        else:
            st.warning("⚠️ 该板块成分股被过滤条件全部拦截。")
            
        with st.expander("🔍 点击查看腾讯财经返回的全部原始数据（未经漏斗）"):
            st.dataframe(df_stocks, use_container_width=True)
    else:
        st.error("未能获取数据。可能是休市期间或板块内暂无股票。")
else:
    st.error("无法获取板块字典。请检查网络环境或稍后再试。")
