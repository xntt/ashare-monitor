import streamlit as st
import pandas as pd
import requests
import re
import json

# ==========================================
# 1. 隔夜美股风向标 (新浪极速接口)
# ==========================================
@st.cache_data(ttl=600)
def get_us_mapping_sina():
    us_tickers = {
        "gb_nvda": "英伟达(算力)", "gb_tsla": "特斯拉(机器人)", 
        "gb_aapl": "苹果(消费电子)", "gb_spce": "维珍银河(航天)"
    }
    url = "http://hq.sinajs.cn/list=" + ",".join(us_tickers.keys())
    headers = {'Referer': 'https://finance.sina.com.cn'}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'gbk'
        lines = response.text.strip().split('\n')
        
        us_data = []
        for line in lines:
            if '="' in line:
                code_part = line.split('=')[0].split('_')[-1]
                data_str = line.split('="')[1].strip('";')
                cols = data_str.split(',')
                if len(cols) > 2:
                    name = us_tickers.get(f"gb_{code_part}")
                    us_data.append({
                        "标的": name, 
                        "最新价": float(cols[1]), 
                        "涨跌幅(%)": float(cols[2])
                    })
        return pd.DataFrame(us_data)
    except Exception as e:
        return pd.DataFrame([{"错误": f"新浪美股拉取失败: {e}"}])

# ==========================================
# 2. 核心：新浪全量快照大杀器 (一次性拉取5000+只A股)
# ==========================================
@st.cache_data(ttl=300) # 存档功能：缓存5分钟，这5分钟内不管怎么调整参数都不需要重新拉取！
def fetch_all_market_snapshot_sina():
    """
    利用新浪财经隐藏接口，单次请求 6000 条数据，覆盖整个沪深A股。
    """
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {
        "page": "1",
        "num": "6000",   # 核心破解点：直接要求返回6000条，覆盖全市场
        "sort": "symbol",
        "asc": "1",
        "node": "hs_a"   # hs_a 代表沪深A股
    }
    
    try:
        res = requests.get(url, params=params, timeout=8)
        res.encoding = 'gbk'
        text = res.text
        
        # 【黑科技修复】新浪返回的JSON格式不规范(键名没有双引号)，用正则给它加上双引号才能解析
        text = re.sub(r'(?<=[{,])([a-zA-Z_]\w*)(?=:)', r'"\1"', text)
        
        raw_data = json.loads(text)
        clean_data = []
        
        for stock in raw_data:
            # 清洗转换函数：如果是空值或异常值，转为0
            def to_float(val, default=0.0):
                try:
                    return float(val)
                except:
                    return default
                    
            # 新浪的总市值单位是"万"，我们除以 10000 转换成"亿"，方便游资看盘子大小
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
        st.error(f"全市场快照拉取失败 (新浪接口): {e}")
        return pd.DataFrame()

# ==========================================
# 3. Streamlit UI 与 毫秒级内存筛选
# ==========================================
st.set_page_config(page_title="V3.1 新浪全量洗库雷达", layout="wide")

st.markdown("### 🦅 V3.1 游资极速洗库雷达 (纯新浪接口 + 本地毫秒级洗库)")

# --- 顶层：美股风向标 ---
us_df = get_us_mapping_sina()
if not us_df.empty and "错误" not in us_df.columns:
    cols = st.columns(len(us_df))
    for idx, row in us_df.iterrows():
        color = "red" if row['涨跌幅(%)'] > 0 else "green"
        arrow = "🔺" if row['涨跌幅(%)'] > 0 else "🔻"
        cols[idx].markdown(f"**{row['标的']}** <span style='color:{color};'> {arrow} {row['涨跌幅(%)']}%</span>", unsafe_allow_html=True)
st.markdown("---")

# --- 右侧侧边栏：核心漏斗控制台 ---
st.sidebar.header("🎯 本地快照洗库漏斗")

st.sidebar.markdown("**第一步：获取/更新市场快照**")
if st.sidebar.button("🔄 拉取全市场最新快照", type="primary"):
    fetch_all_market_snapshot_sina.clear() # 清除缓存，强制重新拉取新浪最新数据
    st.sidebar.success("快照已从新浪服务器更新！")

st.sidebar.markdown("---")
st.sidebar.markdown("**第二步：从存档中实时洗库**")

search_keyword = st.sidebar.text_input("1. 名称包含 (选填，如'科技'、'机器')")

st.sidebar.markdown("**2. 基本面排雷**")
max_pe = st.sidebar.slider("最大市盈率 (PE)", 0, 300, 80, help="0表示过滤掉亏损企业")
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 500, help="游资喜欢盘子小的，船小好掉头")

st.sidebar.markdown("**3. 极致量价买点**")
min_turn = st.sidebar.number_input("最小换手率 (%)", value=3.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 4.0), step=0.5)

# --- 主体区：内存筛选与展示 ---
with st.spinner("正在通过新浪专线加载全市场 5000+ 股票快照..."):
    # 第一次拉取大概需要1~2秒，之后全在内存里瞬间完成
    df_all = fetch_all_market_snapshot_sina()

if not df_all.empty:
    total_stocks = len(df_all)
    
    # 在内存中执行极速漏斗筛选
    df_filtered = df_all.copy()
    
    # 1. 关键词过滤
    if search_keyword:
        df_filtered = df_filtered[df_filtered['名称'].str.contains(search_keyword)]
        
    # 2. 基本面过滤
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    
    # 3. 量价极值过滤
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    
    # 4. 排序：换手率高的（资金最活跃的）排在最前面
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    # --- 渲染结果 ---
    st.success(f"📦 新浪专线已载入全市场 **{total_stocks}** 只股票快照。经过漏斗实时清洗，截获 **{len(df_filtered)}** 只极品标的！")
    
    if not df_filtered.empty:
        # 设置涨红跌绿的样式
        def color_change(val):
            color = 'red' if val > 0 else 'green' if val < 0 else 'gray'
            return f'color: {color}'
            
        styled_df = df_filtered.style.map(color_change, subset=['涨跌幅(%)'])\
                            .format({
                                "最新价": "{:.2f}", 
                                "涨跌幅(%)": "{:.2f}%", 
                                "换手率(%)": "{:.2f}%", 
                                "市盈率(PE)": "{:.1f}", 
                                "市净率(PB)": "{:.2f}",
                                "总市值(亿)": "{:.2f}"
                            })
        
        st.dataframe(styled_df, use_container_width=True, height=600)
    else:
        st.warning("⚠️ 存档中暂无满足当前条件的数据，请在左侧侧边栏适当放宽条件（例如放宽市值或市盈率）。")
else:
    st.error("无法获取新浪市场快照，请检查网络设置。")
