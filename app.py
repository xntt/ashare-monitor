import streamlit as st
import pandas as pd
import requests

# ==========================================
# 1. 终极无阻碍：直连东方财富手机App CDN 获取全市场板块
# ==========================================
@st.cache_data(ttl=3600)
def fetch_all_sectors_cdn():
    """
    直接调用东财移动端 CDN 接口，不触碰 Web 防火墙。永不被屏蔽。
    """
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    sectors = {}
    
    try:
        # 1. 抓取所有【概念板块】(代码特征 m:90 t:3)
        params_concept = {
            "pn": 1, "pz": 500, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281", # 东财公开的公共Token
            "fid": "f3", "fs": "m:90+t:3+f:!50", "fields": "f12,f14"
        }
        res_c = requests.get(url, params=params_concept, timeout=5).json()
        if 'data' in res_c and res_c['data'] and 'diff' in res_c['data']:
            for item in res_c['data']['diff']:
                sectors[f"【概念】{item['f14']}"] = item['f12'] # f14:名称, f12:板块代码

        # 2. 抓取所有【行业板块】(代码特征 m:90 t:2)
        params_industry = {
            "pn": 1, "pz": 500, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fid": "f3", "fs": "m:90+t:2+f:!50", "fields": "f12,f14"
        }
        res_i = requests.get(url, params=params_industry, timeout=5).json()
        if 'data' in res_i and res_i['data'] and 'diff' in res_i['data']:
            for item in res_i['data']['diff']:
                sectors[f"【行业】{item['f14']}"] = item['f12']

        return dict(sorted(sectors.items()))
    except Exception as e:
        st.error(f"CDN 节点连接失败: {e}")
        return {}

# ==========================================
# 2. 直连 CDN 极速拉取板块内所有成分股及基本面
# ==========================================
@st.cache_data(ttl=60)
def fetch_stocks_by_cdn(bk_code):
    """
    拿到板块代码后（如 BK0696），直接从 CDN 提取里面所有股票的量价和估值！
    """
    if not bk_code: return pd.DataFrame()
    
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": 500, "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fid": "f8", # 按换手率排序
        "fs": f"b:{bk_code}+f:!50",
        # f12:代码, f14:名称, f2:最新价, f3:涨幅%, f8:换手率, f9:动态PE, f23:市净率, f20:总市值
        "fields": "f12,f14,f2,f3,f8,f9,f20,f23" 
    }
    
    try:
        res = requests.get(url, params=params, timeout=5).json()
        clean_data = []
        
        if 'data' in res and res['data'] and 'diff' in res['data']:
            for stock in res['data']['diff']:
                def to_float(val, default=0.0):
                    # 东财 API 在停牌或亏损时会返回 "-"
                    if val == "-" or val is None: return default
                    try: return float(val)
                    except: return default
                
                # 东财的总市值 f20 单位是元，除以 1亿 转换
                mkt_cap_yi = round(to_float(stock.get('f20')) / 100000000, 2)
                
                clean_data.append({
                    "代码": str(stock.get('f12', '')),
                    "名称": str(stock.get('f14', '')),
                    "最新价": to_float(stock.get('f2')),
                    "涨跌幅(%)": to_float(stock.get('f3')),
                    "换手率(%)": to_float(stock.get('f8')),
                    "市盈率(PE)": to_float(stock.get('f9')),
                    "市净率(PB)": to_float(stock.get('f23')),
                    "总市值(亿)": mkt_cap_yi
                })
        return pd.DataFrame(clean_data)
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. Streamlit 渲染界面
# ==========================================
st.set_page_config(page_title="V7.0 App-CDN 雷达", layout="wide")
st.markdown("### 🦅 V7.0 动态板块雷达 (移动端 CDN 直连抗屏蔽版)")

with st.spinner("📡 正在直连高速 CDN 节点，扫描全网板块字典..."):
    dynamic_sectors = fetch_all_sectors_cdn()

if dynamic_sectors:
    st.sidebar.header("🎯 第一步：搜索/选择动态板块")
    selected_sector_name = st.sidebar.selectbox(
        "支持输入关键词搜索 (例如: 具身智能 / 芯片)：", 
        list(dynamic_sectors.keys())
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 第二步：量化过滤漏斗")
    max_pe = st.sidebar.slider("最大市盈率 (PE)", 0, 300, 100, help="0表示过滤亏损")
    max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)

    st.sidebar.markdown("**游资量价买点**")
    min_turn = st.sidebar.number_input("最小换手率 (%)", value=2.0, step=0.5)
    price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (0.0, 5.0), step=0.5)

    bk_code = dynamic_sectors.get(selected_sector_name)
    st.markdown(f"#### 正在监控：**{selected_sector_name}** (CDN板块代码: `{bk_code}`)")
    
    with st.spinner(f"正在从 CDN 高速拉取 {selected_sector_name} 的全部成分股..."):
        df_stocks = fetch_stocks_by_cdn(bk_code)

    if not df_stocks.empty:
        df_filtered = df_stocks.copy()
        df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
        df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
        df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
        df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
        df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
        
        st.markdown(f"📦 CDN 返回 **{len(df_stocks)}** 只成分股。经过漏斗截获 **{len(df_filtered)}** 只标的！")
        
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
            st.warning("⚠️ 该板块成分股被漏斗全部拦截，请放宽左侧条件。")
            
        with st.expander("🔍 点击查看 CDN 返回的全部原始数据（无过滤）"):
            st.dataframe(df_stocks, use_container_width=True)
    else:
        st.error("暂无数据。可能是停牌、闭市或板块无股票。")
else:
    st.error("网络连接失败，请刷新页面。")
