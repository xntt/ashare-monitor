import streamlit as st
import pandas as pd
import requests
import random

# ==========================================
# 0. 腾讯防封锁请求头伪装
# ==========================================
def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://finance.qq.com/"
    }

# ==========================================
# 1. 100% 腾讯接口：全自动动态扫描“所有板块” 
# ==========================================
@st.cache_data(ttl=3600)
def fetch_tencent_sectors():
    """
    直接调用腾讯财经 App/小程序的底层 API，获取最新的板块目录。
    绝对没有一行写死的数据！
    """
    # 腾讯板块目录 API
    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/chg_center/getBoard"
    sectors = {}
    
    try:
        # 1. 自动扫描腾讯的【概念板块】(board=gn)
        res_gn = requests.get(url, params={"board": "gn"}, headers=get_headers(), timeout=5).json()
        if res_gn.get("code") == 0:
            for item in res_gn["data"]["board_list"]:
                sectors[f"【概念】{item['name']}"] = item['code']

        # 2. 自动扫描腾讯的【行业板块】(board=hy)
        res_hy = requests.get(url, params={"board": "hy"}, headers=get_headers(), timeout=5).json()
        if res_hy.get("code") == 0:
            for item in res_hy["data"]["board_list"]:
                sectors[f"【行业】{item['name']}"] = item['code']

        return dict(sorted(sectors.items()))
    except Exception as e:
        st.error(f"腾讯板块目录扫描失败，请检查网络: {e}")
        return {}

# ==========================================
# 2. 100% 腾讯接口：拉取指定板块的全部股票及基本面
# ==========================================
@st.cache_data(ttl=60)
def fetch_tencent_stocks_by_board(board_code):
    """
    第一步：找腾讯小程序 API 拿板块里的所有股票代码
    第二步：拿着代码去腾讯极速接口 (qt.gtimg.cn) 拉取量价和 PE、市值
    """
    if not board_code: return pd.DataFrame()
    
    # --- Step 1: 获取板块内所有股票代码 ---
    rank_url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/chg_center/getBoardRank"
    try:
        res = requests.get(rank_url, params={"board": board_code}, headers=get_headers(), timeout=5).json()
        if res.get("code") != 0:
            return pd.DataFrame()
            
        # 提取股票代码 (腾讯返回的格式通常是 sh600000 或 sz000001)
        symbol_list = [item['symbol'] for item in res["data"]["rank_list"]]
    except Exception as e:
        st.error(f"获取腾讯板块成分股失败: {e}")
        return pd.DataFrame()

    if not symbol_list:
        return pd.DataFrame()

    # --- Step 2: 去腾讯极速接口批量获取详细数据 ---
    # 腾讯接口每次最多查 100 个代码，防止 URL 太长
    clean_data = []
    
    # 将列表切割成每份 100 个的批次
    chunk_size = 100
    for i in range(0, len(symbol_list), chunk_size):
        chunk = symbol_list[i:i + chunk_size]
        tencent_qt_url = f"http://qt.gtimg.cn/q={','.join(chunk)}"
        
        try:
            t_res = requests.get(tencent_qt_url, headers=get_headers(), timeout=5)
            t_res.encoding = 'gbk' # 腾讯极速接口是 GBK 编码
            lines = t_res.text.strip().split('\n')
            
            for line in lines:
                if not line or "=" not in line: continue
                
                # 解析腾讯极速格式：v_sh600519="1~贵州茅台~600519~..."
                data_str = line.split('=')[1].replace('"', '')
                fields = data_str.split('~')
                
                if len(fields) < 47: continue # 过滤停牌等异常数据
                
                def to_float(val, default=0.0):
                    try: return float(val)
                    except: return default

                clean_data.append({
                    "代码": fields[2],
                    "名称": fields[1],
                    "最新价": to_float(fields[3]),
                    "涨跌幅(%)": to_float(fields[32]),     # 字段32: 涨跌幅
                    "换手率(%)": to_float(fields[38]),     # 字段38: 换手率
                    "市盈率(PE)": to_float(fields[39]),    # 字段39: 动态市盈率
                    "市净率(PB)": to_float(fields[46]),    # 字段46: 市净率
                    "总市值(亿)": to_float(fields[45]),    # 字段45: 总市值(亿)
                })
        except Exception as e:
            continue # 忽略单批次错误，继续查下一批

    return pd.DataFrame(clean_data)

# ==========================================
# 3. Streamlit UI 界面与量化漏斗
# ==========================================
st.set_page_config(page_title="V8.0 纯腾讯极速雷达", layout="wide")
st.markdown("### 🐧 V8.0 纯血腾讯财经动态雷达 (100%抗屏蔽)")

# --- 执行板块扫描 ---
with st.spinner("📡 正在调用腾讯小程序底层 API，扫描全网板块..."):
    dynamic_sectors = fetch_tencent_sectors()

if dynamic_sectors:
    st.sidebar.header("🎯 第一步：搜索动态板块")
    selected_sector_name = st.sidebar.selectbox(
        "输入关键词或下拉选择 (例如: 算力 / 低空)：", 
        list(dynamic_sectors.keys())
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 第二步：量化过滤漏斗")
    max_pe = st.sidebar.slider("最大市盈率 (PE)", 0, 300, 100, help="0表示过滤亏损")
    max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)

    st.sidebar.markdown("**游资量价买点**")
    min_turn = st.sidebar.number_input("最小换手率 (%)", value=2.0, step=0.5)
    price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 5.0), step=0.5)

    board_code = dynamic_sectors.get(selected_sector_name)
    st.markdown(f"#### 当前板块：**{selected_sector_name}** (腾讯代码: `{board_code}`)")
    
    # --- 拉取数据并过滤 ---
    with st.spinner(f"正在向腾讯极速接口批量请求 {selected_sector_name} 实时数据..."):
        df_stocks = fetch_tencent_stocks_by_board(board_code)

    if not df_stocks.empty:
        # 内存漏斗清洗
        df_filtered = df_stocks.copy()
        df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
        df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
        df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
        df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
        df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
        
        st.markdown(f"📦 腾讯极速接口返回 **{len(df_stocks)}** 只成分股。漏斗清洗截获 **{len(df_filtered)}** 只标的！")
        
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
            st.warning("⚠️ 该板块成分股被漏斗全部拦截，请在左侧放宽条件。")
            
        with st.expander("🔍 点击查看腾讯返回的该板块全部原始数据（未经漏斗）"):
            st.dataframe(df_stocks, use_container_width=True)
    else:
        st.error("暂无数据。可能是休市期间或该板块暂无股票。")
else:
    st.error("腾讯板块字典获取失败。请检查网络。")
