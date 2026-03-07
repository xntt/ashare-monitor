import streamlit as st
import requests
import json
import re
import pandas as pd

# ================= 网页基础设置 =================
st.set_page_config(page_title="个股双引擎雷达", page_icon="🎯", layout="wide")

st.title("🎯 盘后个股雷达：双引擎扫描系统")
st.markdown("数据源：新浪财经高速直连 (脱离东方财富/Akshare) | 包含 5000 只 A 股")

# ================= 核心引擎：新浪财经全市场抓取 =================
@st.cache_data(ttl=3600) # 缓存1小时，避免每次点击网页都重新下载5000只股票
def get_sina_all_stocks():
    all_data = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # 用 Streamlit 的进度条让等待不枯燥
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for page in range(1, 80):
        url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=80&sort=symbol&asc=1&node=hs_a"
        try:
            response = requests.get(url, headers=headers, timeout=5)
            text = response.text
            
            if text == "null" or text == "[]" or not text:
                break
                
            text = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', text)
            data = json.loads(text)
            all_data.extend(data)
            
            # 更新网页上的进度条 (假设最多70页)
            progress = min(page / 70.0, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"📡 正在拉取全市场数据... (第 {page} 页)")
            
        except Exception as e:
            break
            
    progress_bar.empty()
    status_text.empty()
    
    df = pd.DataFrame(all_data)
    if df.empty:
        return pd.DataFrame()

    # 数据格式清洗
    df['换手率'] = pd.to_numeric(df['turnoverratio'], errors='coerce')
    df['涨跌幅'] = pd.to_numeric(df['changepercent'], errors='coerce')
    df['最新价'] = pd.to_numeric(df['trade'], errors='coerce')
    df['流通市值_亿'] = pd.to_numeric(df['nmc'], errors='coerce') * 10000 / 1_0000_0000 
    df['代码'] = df['symbol'].str.replace('sh', '').str.replace('sz', '')
    df['名称'] = df['name']
    
    # 基础剔除
    df = df[~df['名称'].str.contains('ST|退', na=False)]
    df = df[~df['代码'].str.startswith('8', na=False)]
    df = df[df['换手率'] > 0] 
    
    return df

# ================= 界面控制与展示模块 =================
# 添加一个大按钮，只有点击才会去扫描
if st.button("🚀 启动今日 A 股雷达扫描 (约需10秒)", type="primary"):
    
    with st.spinner('正在从新浪节点下载并清洗 5000 只股票快照...'):
        df_all = get_sina_all_stocks()
        
    if df_all.empty:
        st.error("❌ 数据拉取失败，可能是网络问题。")
    else:
        st.success(f"✅ 成功获取 {len(df_all)} 只活跃 A 股数据！请在下方两个独立板块查看：")
        
        # 核心需求：用 Tab 标签页实现【界面的绝对物理隔离】
        tab1, tab2 = st.tabs(["🪦 模块一：个股·底线拾荒池 (找错杀)", "🔥 模块二：个股·概念突变池 (抓妖股)"])
        
        # ----------------- 模块一：底线拾荒池 -----------------
        with tab1:
            st.info("💡 过滤逻辑：换手率极度低迷（<1%）、股价心电图横盘震荡。全是死气沉沉的票，去找里面的金子。")
            
            bottom_pool = df_all[
                (df_all['换手率'] <= 1.0) & 
                (df_all['涨跌幅'].between(-1.5, 1.5)) & 
                (df_all['流通市值_亿'] > 30)
            ].sort_values(by='换手率').head(30).copy()
            
            bottom_pool['形态特征'] = "🪦 极致缩量/僵尸状"
            bottom_pool['核心工业区(省份)'] = "需去同花顺F10查"
            bottom_pool['机构控盘度'] = "查看十大流通股东"
            
            bottom_show = bottom_pool[['代码', '名称', '最新价', '涨跌幅', '换手率', '流通市值_亿', '形态特征', '核心工业区(省份)', '机构控盘度']]
            bottom_show.columns = ['代码', '简称', '最新价', '涨跌幅(%)', '换手率(%)', '流通市值(亿)', '形态特征', '📍省份防雷', '🏢机构防雷']
            
            # 在网页上展示漂亮的表格
            st.dataframe(bottom_show, use_container_width=True, hide_index=True)

        # ----------------- 模块二：概念突变池 -----------------
        with tab2:
            st.error("💡 过滤逻辑：今日换手爆量（>8%）、强势首板或逼近涨停。隐藏原有无聊概念，去同花顺搜今天谁传了小作文。")
            
            mutation_pool = df_all[
                (df_all['换手率'] >= 8.0) & 
                (df_all['涨跌幅'] >= 9.0) & 
                (df_all['流通市值_亿'] < 100)
            ].sort_values(by='换手率', ascending=False).copy()
            
            mutation_pool['突发异变原因'] = "待同花顺F10确认 (隐藏冗杂)"
            mutation_pool['今日异动特征'] = "🚀 爆量涨停 (疑似起爆)"
            mutation_pool['复盘动作'] = "去互动易搜：小作文 / 拿到谁的订单"
            
            mutation_show = mutation_pool[['代码', '名称', '涨跌幅', '换手率', '流通市值_亿', '突发异变原因', '今日异动特征', '复盘动作']]
            mutation_show.columns = ['代码', '简称', '涨跌幅(%)', '换手率(%)', '流通市值(亿)', '💥新增爆点标签', '📊量价特征', '复盘动作']
            
            # 在网页上展示漂亮的表格
            st.dataframe(mutation_show, use_container_width=True, hide_index=True)
