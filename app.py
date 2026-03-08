import streamlit as st
import pandas as pd
import requests

# ==========================================
# 1. 本地核心资产库 (防封杀的“外脑”底座)
# ==========================================
THEMES_DB = {
    "🔥 英伟达/算力产业链 (光模块/液冷/服务器)": [
        "sh601138", "sz300308", "sz300502", "sz000938", "sh600584", "sz300394", "sh603083", "sz002463", "sz300474", "sh600487"
    ],
    "🤖 具身智能/特斯拉机器人 (减速器/电机/执行器)": [
        "sz002050", "sh600580", "sh603019", "sz002122", "sz002284", "sh603960", "sz300161", "sz002031", "sh601689"
    ],
    "🛸 SpaceX/低空经济 (商业航天/飞行汽车)": [
        "sh600862", "sz002389", "sz300993", "sz002985", "sh600118", "sz300589", "sh600391", "sz002380"
    ],
    "🛡️ 国家队/低位高股息 (防守反击/汇金底牌)": [
        "sh601088", "sh601988", "sh601288", "sh600900", "sh600028", "sh601006", "sh600104", "sz000338", "sh601111"
    ]
}

# ==========================================
# 2. 数据获取：新浪财经 (获取美股隔夜映射) - 绝对不被墙！
# ==========================================
@st.cache_data(ttl=600) # 缓存10分钟
def get_us_mapping_sina():
    # 新浪美股代码规则：gb_ + 股票代码小写
    us_tickers = {
        "gb_nvda": "英伟达(算力)", 
        "gb_tsla": "特斯拉(机器人)", 
        "gb_aapl": "苹果(消费电子)", 
        "gb_spce": "维珍银河(航天)"
    }
    
    url = "http://hq.sinajs.cn/list=" + ",".join(us_tickers.keys())
    # 新浪接口必须加 Referer 防盗链，否则不返回数据
    headers = {'Referer': 'https://finance.sina.com.cn'}
    
    try:
        response = requests.get(url, headers=headers, timeout=3)
        response.encoding = 'gbk'
        lines = response.text.strip().split('\n')
        
        us_data = []
        for line in lines:
            if '="' in line:
                # 解析新浪美股格式
                code_part = line.split('=')[0].split('_')[-1] # nvda
                data_str = line.split('="')[1].strip('";')
                cols = data_str.split(',')
                
                if len(cols) > 2:
                    name = us_tickers.get(f"gb_{code_part}")
                    price = float(cols[1])      # 最新价
                    change_pct = float(cols[2]) # 涨跌幅
                    
                    us_data.append({
                        "标的": name, 
                        "最新收盘价": price, 
                        "涨跌幅(%)": change_pct
                    })
        return pd.DataFrame(us_data)
    except Exception as e:
        return pd.DataFrame([{"错误": f"新浪美股接口请求失败: {e}"}])

# ==========================================
# 3. 数据获取：腾讯极速批量 API (A股基本面+量价)
# ==========================================
def fetch_tencent_batch_data(stock_codes):
    if not stock_codes:
        return pd.DataFrame()
    
    codes_str = ",".join(stock_codes)
    url = f"http://qt.gtimg.cn/q={codes_str}"
    
    try:
        response = requests.get(url, timeout=3)
        response.encoding = 'gbk'
        lines = response.text.strip().split('\n')
        
        results = []
        for line in lines:
            if not line or "=" not in line:
                continue
            data_str = line.split("=")[1].strip('"')
            cols = data_str.split("~")
            
            if len(cols) > 46:
                try:
                    results.append({
                        "代码": cols[2],
                        "名称": cols[1],
                        "最新价": float(cols[3]),
                        "涨跌幅(%)": float(cols[32]),     # 字段32：涨跌幅
                        "换手率(%)": float(cols[38]),     # 字段38：换手率
                        "市盈率(PE)": float(cols[39]) if cols[39] else 0.0,
                        "市净率(PB)": float(cols[46]) if cols[46] else 0.0
                    })
                except ValueError:
                    continue
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"腾讯A股接口请求失败: {e}")
        return pd.DataFrame()

# ==========================================
# 4. Streamlit 界面与主循环
# ==========================================
st.set_page_config(page_title="V2.1 游资顶层架构雷达", layout="wide")

st.markdown("### 🦅 V2.1 顶层游资雷达 (纯血无依赖版：新浪美股 + 腾讯A股)")

# --- 模块 A：隔夜美股风向标 (新浪接口) ---
st.write("#### 🌍 第一步：隔夜美股风向标 (决定今日主攻叙事)")
us_df = get_us_mapping_sina()

if not us_df.empty and "错误" not in us_df.columns:
    cols = st.columns(len(us_df))
    for idx, row in us_df.iterrows():
        color = "red" if row['涨跌幅(%)'] > 0 else "green"
        arrow = "🔺" if row['涨跌幅(%)'] > 0 else "🔻"
        cols[idx].markdown(f"**{row['标的']}**<br><span style='color:{color}; font-size: 20px;'>{arrow} {row['涨跌幅(%)']}%</span>", unsafe_allow_html=True)
elif "错误" in us_df.columns:
    st.warning(us_df.iloc[0]["错误"])
else:
    st.warning("美股数据暂未开盘或拉取为空")

st.markdown("---")

# --- 模块 B：漏斗控制台 ---
st.sidebar.header("🎯 核心漏斗设置")
selected_theme = st.sidebar.selectbox("1. 锁定今日炒作主线 (核心资产池)", list(THEMES_DB.keys()))

st.sidebar.markdown("**2. 腾讯基本面防雷 (剔除垃圾)**")
max_pe = st.sidebar.slider("剔除高估值 (最大市盈率限制)", 10, 200, 80)
require_pb = st.sidebar.checkbox("要求低破净资产防守 (PB < 2)", value=False)

st.sidebar.markdown("**3. 量价入场点筛选 (防接盘)**")
min_turnover = st.sidebar.number_input("最小换手率 (%) - 需资金活跃", value=2.0)
max_change = st.sidebar.number_input("最大涨幅限制 (%) - 拒绝追高", value=4.0)
min_change = st.sidebar.number_input("最小涨幅限制 (%) - 底部启动", value=0.0)

# --- 模块 C：系统运转与渲染 ---
if st.button("🚀 启动三层漏斗扫描", type="primary"):
    with st.spinner("系统正在进行: 读取核心库 -> 腾讯基本面排雷 -> 量价筛选..."):
        
        target_codes = THEMES_DB[selected_theme]
        df = fetch_tencent_batch_data(target_codes)
        
        if not df.empty:
            initial_count = len(df)
            
            # 漏斗 2：基本面排雷 (PE为0通常代表亏损，也被剔除)
            df = df[(df['市盈率(PE)'] > 0) & (df['市盈率(PE)'] <= max_pe)]
            if require_pb:
                df = df[(df['市净率(PB)'] > 0) & (df['市净率(PB)'] <= 2.0)]
            
            # 漏斗 3：量价极值
            df = df[df['换手率(%)'] >= min_turnover]
            df = df[(df['涨跌幅(%)'] >= min_change) & (df['涨跌幅(%)'] <= max_change)]
            
            # 按换手率排序，寻找最活跃资金
            df = df.sort_values(by="换手率(%)", ascending=False)
            
            st.success(f"🎯 扫描完毕！在【{selected_theme}】的 {initial_count} 只纯正标的中，成功截获 {len(df)} 只符合顶级游资买点法则的极品！")
            
            if not df.empty:
                def color_change(val):
                    color = 'red' if val > 0 else 'green' if val < 0 else 'gray'
                    return f'color: {color}'
                
                styled_df = df.style.map(color_change, subset=['涨跌幅(%)'])\
                                    .format({"涨跌幅(%)": "{:.2f}%", "换手率(%)": "{:.2f}%", "市盈率(PE)": "{:.1f}", "市净率(PB)": "{:.2f}"})
                
                st.dataframe(styled_df, use_container_width=True, height=400)
            else:
                st.info("⚠️ 当前主线内，暂无满足所有条件的标的。建议：适当放宽市盈率或涨跌幅要求。")
                
        else:
            st.error("❌ 数据拉取失败，请检查网络或稍后再试。")
