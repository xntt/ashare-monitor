import streamlit as st
import requests
import json
import re
import pandas as pd

# ================= 网页基础设置 =================
st.set_page_config(page_title="A股防雷达", page_icon="🎯", layout="wide")
st.title("🎯 盘后个股雷达：防接盘扫描系统")
st.markdown("数据源：新浪财经 | **核心准则：拒绝万年僵尸，拒绝高位接盘**")

@st.cache_data(ttl=3600)
def get_sina_all_stocks():
    all_data = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for page in range(1, 80):
        url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=80&sort=symbol&asc=1&node=hs_a"
        try:
            response = requests.get(url, headers=headers, timeout=5)
            text = response.text
            if text == "null" or text == "[]" or not text: break
            text = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', text)
            all_data.extend(json.loads(text))
            
            progress = min(page / 70.0, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"📡 正在拉取全市场数据... (第 {page} 页)")
        except: break
            
    progress_bar.empty()
    status_text.empty()
    
    df = pd.DataFrame(all_data)
    if df.empty: return pd.DataFrame()

    # 清洗数据
    df['换手率'] = pd.to_numeric(df['turnoverratio'], errors='coerce')
    df['涨跌幅'] = pd.to_numeric(df['changepercent'], errors='coerce')
    df['最新价'] = pd.to_numeric(df['trade'], errors='coerce')
    df['流通市值_亿'] = pd.to_numeric(df['nmc'], errors='coerce') * 10000 / 1_0000_0000 
    df['代码'] = df['symbol'].str.replace('sh', '').str.replace('sz', '')
    df['名称'] = df['name']
    
    # 基础剔除：ST、退市、北交所(8开头)、高价股(>100元，没性价比)
    df = df[~df['名称'].str.contains('ST|退', na=False)]
    df = df[~df['代码'].str.startswith('8', na=False)]
    df = df[df['最新价'] <= 100]
    df = df[df['换手率'] > 0] 
    return df

# ================= 界面控制 =================
if st.button("🚀 启动实战扫描 (规避僵尸/规避追高)", type="primary"):
    with st.spinner('正在全市场扫描 5000 只股票...'):
        df_all = get_sina_all_stocks()
        
    if df_all.empty:
        st.error("❌ 数据拉取失败。")
    else:
        st.success("✅ 扫描完成！请在下方查看过滤结果：")
        tab1, tab2 = st.tabs(["📉 模块一：中盘细分龙头·底线地量 (找真企稳)", "🔥 模块二：异动点火期 (拒绝涨停接盘)"])
        
        # ----------------- 模块一：真正的错杀企稳 -----------------
        with tab1:
            st.info("💡 逻辑：市值 100-500亿（有基本面，非僵尸巨无霸），微跌或微涨（-2%到1.5%），换手率极低（0.5%-2%卖盘枯竭）。去日线图看是否连跌后首现十字星。")
            
            bottom_pool = df_all[
                (df_all['流通市值_亿'].between(100, 500)) &  # 规避垃圾股和万年僵尸大盘股
                (df_all['涨跌幅'].between(-2.0, 1.5)) &      # 拒绝暴跌，只需微弱横盘
                (df_all['换手率'].between(0.5, 2.0))        # 卖盘枯竭的极致表现
            ].sort_values(by='换手率').head(25).copy()
            
            bottom_pool['实战复盘建议'] = "看日K：是否偏离均线过远？是否有圆弧底迹象？"
            
            bottom_show = bottom_pool[['代码', '名称', '最新价', '涨跌幅', '换手率', '流通市值_亿', '实战复盘建议']]
            bottom_show.columns = ['代码', '简称', '最新价', '涨跌幅(%)', '换手率(%)', '流通市值(亿)', '🕵️‍♂️ 人工排雷复盘']
            st.dataframe(bottom_show, use_container_width=True, hide_index=True)

        # ----------------- 模块二：异动点火期 -----------------
        with tab2:
            st.error("💡 逻辑：涨幅 3%~6% (安全区间，拒绝涨停接盘)，换手 5%~12% (资金刚进场)，市值 50-200亿 (规避微盘庄股)。去搜同花顺今天出啥利好了。")
            
            mutation_pool = df_all[
                (df_all['涨跌幅'].between(3.0, 6.0)) &       # 只吃腰部利润，拒绝去封板接盘
                (df_all['换手率'].between(5.0, 12.0)) &      # 温和放量，未到死亡换手
                (df_all['流通市值_亿'].between(50, 200))     # 盘子适中，游资散户都能进出
            ].sort_values(by='涨跌幅', ascending=False).head(30).copy()
            
            mutation_pool['实战复盘建议'] = "去F10查：是不是今天出了小作文？或者所属板块今天大热？"
            
            mutation_show = mutation_pool[['代码', '名称', '最新价', '涨跌幅', '换手率', '流通市值_亿', '实战复盘建议']]
            mutation_show.columns = ['代码', '简称', '最新价', '涨跌幅(%)', '换手率(%)', '流通市值(亿)', '🕵️‍♂️ 寻找启动逻辑']
            st.dataframe(mutation_show, use_container_width=True, hide_index=True)
