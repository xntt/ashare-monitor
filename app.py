import streamlit as st
import pandas as pd
import requests
import re
import json

# ==========================================
# 1. 核心大招：全自动动态扫描“所有板块” (纯新浪接口)
# ==========================================
@st.cache_data(ttl=3600) # 每小时自动重新扫描一次全网新概念
def fetch_dynamic_sectors():
    """
    不写死任何数据！通过正则表达式直接暴力破解新浪的动态节点字典，
    将所有最新的【概念板块】和【行业板块】全自动抓取并归类。
    """
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    sector_dict = {}
    try:
        res = requests.get(url, timeout=8)
        text = res.text
        
        # 1. 自动提取所有【概念板块】 (新浪的代码特征是 chgn_开头)
        for part in text.split('chgn_')[1:]:
            code_match = re.match(r'^(\d+)', part)
            # 无视极其不规范的 JSON 格式，直接暴力正则提取中文名
            name_match = re.search(r'name(?:["\']|\s|:)*["\']([^"\']+)["\']', part)
            if code_match and name_match:
                sector_dict[f"【概念】{name_match.group(1)}"] = f"chgn_{code_match.group(1)}"
                
        # 2. 自动提取所有【行业板块】 (新浪的代码特征是 new_bl_开头)
        for part in text.split('new_bl_')[1:]:
            code_match = re.match(r'^(\d+)', part)
            name_match = re.search(r'name(?:["\']|\s|:)*["\']([^"\']+)["\']', part)
            if code_match and name_match:
                sector_dict[f"【行业】{name_match.group(1)}"] = f"new_bl_{code_match.group(1)}"
                
        # 将提取到的 300+ 板块按拼音或名字排序，方便查看
        return dict(sorted(sector_dict.items()))
    except Exception as e:
        st.error(f"动态板块网络扫描失败: {e}")
        return {"错误: 无法获取动态板块": ""}

# ==========================================
# 2. 实时拉取指定板块的全部成分股 (纯新浪极速接口)
# ==========================================
@st.cache_data(ttl=60) # 缓存1分钟，防频繁刷新
def fetch_stocks_by_node(node_code):
    """
    用户点选任意动态板块后，系统自动拿着代码去新浪拉取里面的所有股票及基本面。
    """
    if not node_code or "错误" in node_code:
        return pd.DataFrame()
        
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {
        "page": "1",
        "num": "500",  # 一个板块最多拉500只，足够了
        "sort": "changeprecent",
        "asc": "0",
        "node": node_code
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        res.encoding = 'gbk'
        text = res.text
        
        # 修复新浪残缺的 JSON 键名
        text = re.sub(r'(?<=[{,])([a-zA-Z_]\w*)(?=:)', r'"\1"', text)
        data = json.loads(text)
        
        clean_data = []
        for stock in data:
            def to_float(val, default=0.0):
                try: return float(val)
                except: return default
                
            mkt_cap_yi = round(to_float(stock.get('mktcap')) / 10000, 2)
            clean_data.append({
                "代码": stock.get('symbol', ''),
                "名称": stock.get('name', ''),
                "最新价": to_float(stock.get('trade')),
                "涨跌幅(%)": to_float(stock.get('changepercent')),
                "换手率(%)": to_float(stock.get('turnoverratio')),
                "市盈率(PE)": to_float(stock.get('per')),
                "市净率(PB)": to_float(stock.get('pb')),
                "总市值(亿)": mkt_cap_yi
            })
        return pd.DataFrame(clean_data)
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. Streamlit UI 界面渲染
# ==========================================
st.set_page_config(page_title="V5.0 动态板块扫描雷达", layout="wide")

st.markdown("### 🦅 V5.0 纯动态板块扫描雷达 (全市场自动归类)")

# --- 核心：全自动板块获取 ---
with st.spinner("📡 正在向全网发送雷达波，扫描最新板块/概念..."):
    dynamic_sectors = fetch_dynamic_sectors()

if dynamic_sectors:
    st.success(f"📡 扫描完成！系统已自动获取并归类全市场 **{len(dynamic_sectors)}** 个实时板块。")
    
    # --- 侧边栏：搜索与漏斗 ---
    st.sidebar.header("🎯 第一步：搜索/选择动态板块")
    
    # Streamlit 的 selectbox 自带搜索功能！用户可以直接打字搜“机器人”或“低空”
    selected_sector_name = st.sidebar.selectbox(
        "输入关键词或下拉选择：", 
        list(dynamic_sectors.keys())
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 第二步：量化过滤漏斗")
    st.sidebar.markdown("**基本面防雷**")
    max_pe = st.sidebar.slider("最大市盈率 (PE)", 0, 300, 100, help="0表示过滤亏损企业")
    max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)

    st.sidebar.markdown("**游资量价买点**")
    min_turn = st.sidebar.number_input("最小换手率 (%)", value=2.0, step=0.5)
    price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 5.0), step=0.5)

    # --- 主体区：数据获取与极速洗库 ---
    node_code = dynamic_sectors[selected_sector_name]
    st.markdown(f"#### 当前焦点：**{selected_sector_name}** (新浪节点号: `{node_code}`)")
    
    with st.spinner(f"正在拉取 {selected_sector_name} 旗下所有成分股..."):
        df_stocks = fetch_stocks_by_node(node_code)

    if not df_stocks.empty:
        # 在内存中执行漏斗清洗
        df_filtered = df_stocks.copy()
        df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
        df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
        df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
        df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
        df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
        
        # --- 渲染结果 ---
        st.markdown(f"📦 该板块共有 **{len(df_stocks)}** 只成分股。经过漏斗清洗，截获 **{len(df_filtered)}** 只符合游资逻辑的标的！")
        
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
            st.warning("⚠️ 该板块成分股被漏斗全部过滤，请在左侧放宽条件。")
            
        with st.expander("🔍 点击查看该板块的全部原始股票（未经漏斗过滤）"):
            st.dataframe(df_stocks, use_container_width=True)
    else:
        st.error("未能获取该板块内的股票数据。可能是新浪接口无数据。")
else:
    st.error("板块扫描失败，请检查网络设置。")
