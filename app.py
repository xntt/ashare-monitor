import streamlit as st
import pandas as pd
import akshare as ak
import datetime

# ==========================================
# 核心数据引擎 (纯情绪与资金面)
# ==========================================
@st.cache_data(ttl=300)
def get_longhubang_data(date_str):
    """获取指定日期的龙虎榜详情（寻找资金净流入的核心标的）"""
    try:
        # 东方财富-龙虎榜详情接口
        df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
        if df.empty:
            return pd.DataFrame()
            
        # 提取有用字段并清洗
        df = df[["代码", "名称", "涨跌幅", "收盘价", "龙虎榜净买额", "换手率", "上榜原因"]]
        
        # 将数据转为数值型进行排序
        df["龙虎榜净买额"] = pd.to_numeric(df["龙虎榜净买额"], errors="coerce") / 10000.0 # 转换为万元
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")
        
        # 按净买额从大到小排序，只看真金白银流入的
        df = df.sort_values(by="龙虎榜净买额", ascending=False)
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_limit_up_pool(date_str):
    """获取指定日期的涨停板池（寻找连板龙头和炒作小作文）"""
    try:
        # 东方财富-涨停板池接口 (date参数格式: 20231012)
        date_format = date_str.replace("-", "")
        df = ak.stock_zt_pool_em(date=date_format)
        if df.empty:
            return pd.DataFrame()
            
        # 提取连板天数、所属概念（小作文）
        df = df[["代码", "名称", "涨跌幅", "最新价", "换手率", "连板数", "所属行业", "涨停统计"]]
        
        # 处理数据
        df["连板数"] = pd.to_numeric(df["连板数"], errors="coerce").fillna(1)
        
        # 按连板数降序排序，寻找绝对龙头
        df = df.sort_values(by=["连板数", "换手率"], ascending=[False, False])
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 页面与组件渲染
# ==========================================
st.set_page_config(page_title="游资情绪与龙虎榜雷达", layout="wide", initial_sidebar_state="expanded")
st.markdown("### 🐉 A股核心内参：游资龙虎榜 & 情绪梯队雷达")
st.caption("放弃 PE/PB 执念，拥抱 A 股本质：看清资金流向，跟随连板情绪，顺应政策题材！")

# 侧边栏：交易日选择
st.sidebar.header("⏱️ 1. 时间机器")
st.sidebar.caption("提示：龙虎榜数据通常在交易日 17:00 之后才会全量更新。盘中建议查看前一交易日数据。")

# 默认获取最近的交易日（简单处理：如果是周末，往前推。这里提供手动选择）
today = datetime.datetime.now().date()
selected_date = st.sidebar.date_input("选择要复盘的交易日", value=today)
date_str = selected_date.strftime("%Y-%m-%d")

st.sidebar.markdown("---")
st.sidebar.header("🎯 2. 资金漏斗过滤")
min_net_buy = st.sidebar.number_input("龙虎榜最小净买入 (万元)", value=1000, step=1000, help="过滤掉游资只是做T或者净流出的股票")
min_streak = st.sidebar.slider("最少连板数 (抓龙头)", 1, 15, 1, help="1为首板，只看妖股可以调高此数值")

# ==========================================
# 模块一：游资真金白银 —— 龙虎榜净买入追踪
# ==========================================
st.markdown(f"#### 💰 榜单一：【{date_str}】 龙虎榜主力净买入追踪")
with st.spinner("正在从东方财富底层提取龙虎榜游资席位数据..."):
    df_lhb = get_longhubang_data(date_str)

if not df_lhb.empty:
    # 漏斗过滤：只看净买入大于设定值的
    df_lhb_filtered = df_lhb[df_lhb["龙虎榜净买额"] >= min_net_buy]
    
    st.info(f"当天共有 {len(df_lhb)} 只股票上榜，其中净买入超过 {min_net_buy} 万元的硬核资金票有 **{len(df_lhb_filtered)}** 只！")
    
    if not df_lhb_filtered.empty:
        # 样式渲染
        def style_positive(val):
            return f"color: {'red' if val > 0 else 'green' if val < 0 else 'gray'}; font-weight: bold"
            
        st.dataframe(
            df_lhb_filtered.style.map(style_positive, subset=['涨跌幅', '龙虎榜净买额'])\
            .format({"涨跌幅": "{:.2f}%", "换手率": "{:.2f}%", "龙虎榜净买额": "{:.0f} 万"}),
            use_container_width=True, height=350
        )
else:
    st.warning("📭 当前日期没有获取到龙虎榜数据（可能是周末、节假日，或者今天的数据还没更新，请选昨天的日期试试）。")

st.markdown("---")

# ==========================================
# 模块二：市场情绪标尺 —— 涨停连板梯队与题材
# ==========================================
st.markdown(f"#### 🚀 榜单二：【{date_str}】 市场情绪连板梯队 (抓妖股/看小作文)")
with st.spinner("正在扫描全市场涨停板与背后的政策题材..."):
    df_zt = get_limit_up_pool(date_str)

if not df_zt.empty:
    df_zt_filtered = df_zt[df_zt["连板数"] >= min_streak]
    
    # 统计最高连板（寻找市场总龙头）
    max_streak = int(df_zt["连板数"].max())
    
    st.success(f"🔥 当日全市场涨停 **{len(df_zt)}** 家！当前市场最高连板高度：**{max_streak} 连板** （这就是全场总龙头）")
    
    if not df_zt_filtered.empty:
        # 高亮连板数和题材
        def highlight_streak(val):
            if val >= 4: return 'background-color: darkred; color: white; font-weight: bold'
            elif val >= 2: return 'background-color: maroon; color: white'
            return ''

        st.dataframe(
            df_zt_filtered.style.map(highlight_streak, subset=['连板数'])\
            .format({"涨跌幅": "{:.2f}%", "换手率": "{:.2f}%", "连板数": "{:.0f}"}),
            use_container_width=True, height=500
        )
else:
    st.warning("📭 当前日期未获取到涨停池数据。")

# ==========================================
# 底部：交易逻辑提示
# ==========================================
with st.expander("💡 游资接力核心逻辑（必读）", expanded=True):
    st.markdown("""
    1. **看懂梯队**：市场就像金字塔。最高连板是【总龙头】（如7板），往下是【中位股】（3-4板），底层是【首板跟风】。游资的铁律是**买龙头，抛中位，试首板**。
    2. **看懂龙虎榜**：不要光看游资买，要看是不是**净买入（买入额远大于卖出额）**。如果榜上全是“拉萨营业部（散户大本营）”在买，说明主力已经出货，次日大概率大跌；如果是知名游资（如陈小群、炒股养家）主买，次日溢价高。
    3. **看懂题材（小作文）**：榜单二中的【所属行业/概念】决定了风口。如果当天涨停板里有20只都是“低空经济”，那它就是绝对主线，闭着眼睛去主线里找票；如果各个概念只有1-2只涨停，说明市场处于混沌期，管住手。
    """)
