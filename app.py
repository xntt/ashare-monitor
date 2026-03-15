import streamlit as st
import pandas as pd
import akshare as ak

# ==========================================
# 0. 页面配置
# ==========================================
st.set_page_config(page_title="Akshare 终极雷达", layout="wide")
st.markdown("### 🦅 终极版：基于 Akshare + 东方财富全量数据")

# ==========================================
# 1. 动态获取全市场板块 (东方财富实时数据)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_all_boards():
    concepts = []
    industries = []
    try:
        # 获取东方财富所有概念板块
        df_c = ak.stock_board_concept_name_em()
        concepts = df_c['板块名称'].tolist()
    except Exception as e:
        st.error(f"概念板块获取失败: {e}")

    try:
        # 获取东方财富所有行业板块
        df_i = ak.stock_board_industry_name_em()
        industries = df_i['板块名称'].tolist()
    except Exception as e:
        st.error(f"行业板块获取失败: {e}")

    return concepts, industries

# 加载数据
with st.spinner("正在连接东方财富服务器，初始化全量板块目录..."):
    all_concepts, all_industries = fetch_all_boards()

# ==========================================
# 2. 智能分类与置顶 (把你关心的板块永远放前面)
# ==========================================
# 你关心的核心关键词
TARGET_KEYWORDS = ["稀土", "化工", "有色", "低空", "机器人", "固态电池", "人工智能", "算力", "半导体", "汽车", "医疗"]

pinned_boards = []  # 置顶的板块
other_boards = []   # 其他几百个板块

# 扫描概念板块
for c in all_concepts:
    name = f"【概念】{c}"
    if any(kw in c for kw in TARGET_KEYWORDS):
        pinned_boards.append(name)
    else:
        other_boards.append(name)

# 扫描行业板块
for i in all_industries:
    name = f"【行业】{i}"
    if any(kw in i for kw in TARGET_KEYWORDS):
        pinned_boards.append(name)
    else:
        other_boards.append(name)

# 最终下拉框列表：置顶 + 其他所有
dropdown_options = pinned_boards + other_boards

# ==========================================
# 3. 核心获取函数 (Akshare 抓取成分股)
# ==========================================
@st.cache_data(ttl=5) # 5秒短缓存，拒绝卡死
def get_board_stocks(selected_name):
    # 解析出是概念还是行业，以及真实名称
    is_concept = "【概念】" in selected_name
    real_name = selected_name.replace("【概念】", "").replace("【行业】", "")
    
    try:
        if is_concept:
            # 获取东方财富概念板块成分股
            df = ak.stock_board_concept_cons_em(symbol=real_name)
        else:
            # 获取东方财富行业板块成分股
            df = ak.stock_board_industry_cons_em(symbol=real_name)
            
        # 统一规范列名，对接你的量化漏斗
        rename_map = {
            '代码': '代码',
            '名称': '名称',
            '最新价': '最新价',
            '涨跌幅': '涨跌幅(%)',
            '换手率': '换手率(%)',
            '市盈率-动态': '市盈率(PE)',
            '市净率': '市净率(PB)',
            '总市值': '原始总市值'
        }
        df = df.rename(columns=rename_map)
        
        # 将市值换算成“亿”为单位
        if '原始总市值' in df.columns:
            df['总市值(亿)'] = df['原始总市值'] / 100000000.0
        else:
            df['总市值(亿)'] = 0.0
            
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 4. 侧边栏与量化漏斗
# ==========================================
st.sidebar.header("🎯 1. 选择板块 (东方财富源)")
if dropdown_options:
    selected_sector = st.sidebar.selectbox("下拉选择或搜索：", dropdown_options)
else:
    st.sidebar.error("未能加载板块，请检查网络。")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 量化漏斗过滤")
st.sidebar.caption("提示：如主界面无数据，请尝试调低换手率或放宽涨跌幅")
max_pe = st.sidebar.slider("最大动态市盈率 (PE)", 0, 500, 100)
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)
min_turn = st.sidebar.number_input("最小换手率 (%) [填0看全部]", value=2.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (-10.0, 11.0), step=0.5)

# ==========================================
# 5. 数据处理与渲染
# ==========================================
st.markdown(f"#### 正在监控：**{selected_sector}**")

with st.spinner("🚀 正在通过 Akshare 呼叫东方财富接口获取成分股..."):
    df_stocks = get_board_stocks(selected_sector)

if not df_stocks.empty:
    # 开始漏斗过滤
    df_filtered = df_stocks.copy()
    
    # 过滤条件
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    
    # 按换手率降序
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    # 保留核心展示列
    display_cols = ['代码', '名称', '最新价', '涨跌幅(%)', '换手率(%)', '市盈率(PE)', '市净率(PB)', '总市值(亿)']
    df_filtered = df_filtered[[c for c in display_cols if c in df_filtered.columns]]
    
    st.success(f"✅ Akshare底层透视：东方财富该板块共 **{len(df_stocks)}** 只成分股。量化漏斗过滤后剩余 **{len(df_filtered)}** 只！")
    
    if not df_filtered.empty:
        def color_change(val):
            return f"color: {'red' if val > 0 else 'green' if val < 0 else 'gray'}"
            
        # 格式化数据并高亮
        styled_df = df_filtered.style.map(color_change, subset=['涨跌幅(%)'])\
                            .format({
                                "最新价": "{:.2f}", "涨跌幅(%)": "{:.2f}%", 
                                "换手率(%)": "{:.2f}%", "市盈率(PE)": "{:.2f}", 
                                "市净率(PB)": "{:.2f}", "总市值(亿)": "{:.2f}"
                            })
        st.dataframe(styled_df, use_container_width=True, height=450)
    else:
        st.warning("⚠️ 漏斗条件太严啦！数据是有的，只是被左侧的滑块全拦住了。")
        
    with st.expander("🔍 查看：东方财富返回的【全部原始数据】（无视漏斗）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.error("未能获取数据。可能是休市，或者东方财富接口暂未响应，请稍后再试。")
