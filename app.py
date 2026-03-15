import streamlit as st
import pandas as pd
import requests
import re
import json

# ==========================================
# 0. 新浪财经专属板块代码 (拼音缩写/行业代码)
# ==========================================
SINA_SECTORS = {
    "📌【特加】稀土永磁": "concept_xtyc",
    "📌【特加】化工行业(化学制品)": "sinaindustry_42", 
    "📌【特加】有色金属": "sinaindustry_50",
    "【概念】低空经济": "concept_dkjj",      # 注：新概念若新浪未更新可能为空
    "【概念】机器人概念": "concept_jqr",
    "【概念】固态电池": "concept_gtdc",
    "【概念】人工智能": "concept_rgzn",
    "【概念】算力租赁": "concept_slgn",
    "【行业】半导体": "sinaindustry_46",
    "【行业】汽车整车": "sinaindustry_43",
    "【行业】医疗器械": "sinaindustry_38"
}

# ==========================================
# 1. 新浪财经直连引擎 (完全无视拦截)
# ==========================================
@st.cache_data(ttl=15)
def fetch_sina_data(node_code):
    # 新浪财经 VIP 节点，按涨跌幅排序，拉取前 500 只股票
    target_url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=500&sort=changepercent&asc=0&node={node_code}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://finance.sina.com.cn/"
    }

    try:
        # 新浪接口从不拦截，直接使用 requests 裸连即可
        res = requests.get(target_url, headers=headers, timeout=8)
        text = res.text
        
        if not text or text.strip() == "null":
            return pd.DataFrame(), "新浪数据库尚未收录该板块"

        # 黑科技：新浪返回的 JSON 键值没有双引号 (比如 {symbol:"sh600..."})，Python 会报错
        # 我们用正则表达式强行给它的 Key 加上双引号，修复新浪的 JSON
        fixed_text = re.sub(r'([{,])\s*([a-zA-Z_0-9]+)\s*:', r'\1"\2":', text)
        
        raw_json = json.loads(fixed_text)
        
        if not raw_json or len(raw_json) == 0:
            return pd.DataFrame(), "该板块目前为空"
            
        return parse_sina_to_df(raw_json), "新浪财经 VIP 接口直连"
        
    except Exception as e:
        return pd.DataFrame(), f"请求出错: {str(e)[:50]}"

def parse_sina_to_df(raw_json):
    clean_data = []
    for s in raw_json:
        def to_float(val):
            try: return float(val)
            except: return 0.0

        clean_data.append({
            "代码": str(s.get("symbol", "")).replace("sh", "").replace("sz", ""),
            "名称": str(s.get("name", "")),
            "最新价": to_float(s.get("trade")),
            "涨跌幅(%)": to_float(s.get("changepercent")),
            "换手率(%)": to_float(s.get("turnoverratio")),
            "市盈率(PE)": to_float(s.get("per")),
            "市净率(PB)": to_float(s.get("pb")),
            # 新浪的总市值单位是"万元"，需要除以10000转换成"亿元"
            "总市值(亿)": to_float(s.get("mktcap")) / 10000.0
        })
    return pd.DataFrame(clean_data)

# ==========================================
# 2. 页面与组件渲染
# ==========================================
st.set_page_config(page_title="游资板块透视", layout="wide")
st.markdown("### 🦅 游资雷达：新浪财经光速直连版")

st.sidebar.header("🎯 1. 选择板块")
selected_sector = st.sidebar.selectbox("请选择要扫描的板块：", list(SINA_SECTORS.keys()))

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 量化漏斗过滤")
st.sidebar.caption("提示：主界面无数据时，把换手率调到0即可看到所有股")
max_pe = st.sidebar.slider("最大动态市盈率 (PE)", 0, 500, 100)
max_mkt_cap = st.sidebar.slider("最大总市值 (亿)", 10, 5000, 1000)
min_turn = st.sidebar.number_input("最小换手率 (%) [填0看全部]", value=2.0, step=0.5)
price_range = st.sidebar.slider("今日涨跌幅区间 (%)", -10.0, 11.0, (-10.0, 11.0), step=0.5)

node_code = SINA_SECTORS[selected_sector]
st.markdown(f"#### 正在监控：**{selected_sector}** (新浪节点: {node_code})")

# 加载数据
with st.spinner("🚀 正在从新浪财经拉取实时数据 (预计 1~2 秒)..."):
    df_stocks, status_msg = fetch_sina_data(node_code)

if not df_stocks.empty:
    st.success(f"✅ 数据拉取成功！通道状态: **{status_msg}**")
    
    df_filtered = df_stocks.copy()
    
    # 漏斗执行
    df_filtered = df_filtered[(df_filtered['市盈率(PE)'] > 0) & (df_filtered['市盈率(PE)'] <= max_pe)]
    df_filtered = df_filtered[df_filtered['总市值(亿)'] <= max_mkt_cap]
    df_filtered = df_filtered[df_filtered['换手率(%)'] >= min_turn]
    df_filtered = df_filtered[(df_filtered['涨跌幅(%)'] >= price_range[0]) & (df_filtered['涨跌幅(%)'] <= price_range[1])]
    
    # 按换手降序
    df_filtered = df_filtered.sort_values(by="换手率(%)", ascending=False)
    
    st.info(f"📊 该板块共包含 **{len(df_stocks)}** 只股票。漏斗过滤后幸存 **{len(df_filtered)}** 只！")
    
    if not df_filtered.empty:
        def color_change(val):
            return f"color: {'red' if val > 0 else 'green' if val < 0 else 'gray'}"
            
        styled_df = df_filtered.style.map(color_change, subset=['涨跌幅(%)'])\
                            .format({
                                "最新价": "{:.2f}", "涨跌幅(%)": "{:.2f}%", 
                                "换手率(%)": "{:.2f}%", "市盈率(PE)": "{:.2f}", 
                                "市净率(PB)": "{:.2f}", "总市值(亿)": "{:.2f}"
                            })
        st.dataframe(styled_df, use_container_width=True, height=450)
    else:
        st.warning("⚠️ 漏斗条件太苛刻！你把左侧的【最小换手率】改成 0 看看。")
        
    with st.expander("🔍 展开查看：新浪财经返回的【全量原始数据】（无视漏斗）"):
        st.dataframe(df_stocks, use_container_width=True)
else:
    st.warning(f"📭 当前板块暂无数据。")
    st.error(f"系统提示：**{status_msg}**")
    st.info("💡 解释：如果是【低空经济】这种2024年刚出的新概念，新浪财经官方可能还未给它建立专属板块数据库，建议查看其他经典老版块！")
