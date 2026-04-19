import os
import requests
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# =========================
# 页面设置
# =========================
st.set_page_config(page_title="AI Financial Terminal", layout="wide")
st.title("📊 AI Financial Terminal（终端级）")
st.warning("⚠️ 本工具仅供学习与研究参考，不构成任何投资建议。")


# =========================
# 工具函数
# =========================
def detect_market(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if ticker.endswith(".HK"):
        return "港股"
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "A股"
    return "美股"


def safe_date(x):
    try:
        return str(x.date()) if hasattr(x, "date") else str(x)
    except Exception:
        return str(x)


def safe_float(x):
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def pct_growth(current, previous):
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    try:
        return round((current - previous) / abs(previous) * 100, 2)
    except Exception:
        return None


def first_existing(row, candidates):
    for c in candidates:
        if c in row and pd.notna(row.get(c)):
            return row.get(c)
    return None


# =========================
# 数据获取
# =========================
@st.cache_data(ttl=3600)
def get_stock_bundle(ticker: str, history_period: str = "1y"):
    stock = yf.Ticker(ticker)

    info = stock.info if stock.info else {}
    history = stock.history(period=history_period)

    try:
        income = stock.financials.T if stock.financials is not None else pd.DataFrame()
    except Exception:
        income = pd.DataFrame()

    try:
        balance = stock.balance_sheet.T if stock.balance_sheet is not None else pd.DataFrame()
    except Exception:
        balance = pd.DataFrame()

    try:
        cashflow = stock.cashflow.T if stock.cashflow is not None else pd.DataFrame()
    except Exception:
        cashflow = pd.DataFrame()

    return {
        "ticker": ticker,
        "market": detect_market(ticker),
        "info": info,
        "history": history,
        "income": income,
        "balance": balance,
        "cashflow": cashflow,
    }


def build_financial_df(bundle: dict) -> pd.DataFrame:
    income = bundle["income"]
    balance = bundle["balance"]
    cashflow = bundle["cashflow"]
    ticker = bundle["ticker"]

    if income.empty:
        return pd.DataFrame()

    rows = []

    for date in income.index:
        income_row = income.loc[date] if date in income.index else pd.Series(dtype="object")
        balance_row = balance.loc[date] if date in balance.index else pd.Series(dtype="object")
        cash_row = cashflow.loc[date] if date in cashflow.index else pd.Series(dtype="object")

        revenue = first_existing(income_row, ["Total Revenue", "Revenue", "Operating Revenue"])
        net_profit = first_existing(income_row, ["Net Income", "Net Income Common Stockholders", "Net Profit"])
        operating_cf = first_existing(cash_row, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
        receivable = first_existing(balance_row, ["Accounts Receivable", "Receivables", "Accounts Notes Receivable"])
        inventory = first_existing(balance_row, ["Inventory", "Inventories"])

        rows.append({
            "company_name": ticker,
            "report_period": safe_date(date),
            "revenue": safe_float(revenue),
            "net_profit": safe_float(net_profit),
            "operating_cashflow": safe_float(operating_cf),
            "accounts_receivable": safe_float(receivable),
            "inventory": safe_float(inventory),
        })

    df = pd.DataFrame(rows)
    return df.sort_values("report_period", ascending=False).reset_index(drop=True)


# =========================
# 财务分析
# =========================
def analyze_financials(df: pd.DataFrame, ticker: str) -> dict:
    if df is None or df.empty or len(df) < 2:
        return {"error": "财报期数不足，无法完成分析"}

    current = df.iloc[0]
    previous = df.iloc[1]

    revenue_yoy = pct_growth(current.get("revenue"), previous.get("revenue"))
    ar_yoy = pct_growth(current.get("accounts_receivable"), previous.get("accounts_receivable"))
    inventory_yoy = pct_growth(current.get("inventory"), previous.get("inventory"))
    profit_yoy = pct_growth(current.get("net_profit"), previous.get("net_profit"))

    risks = []
    memory_notes = []

    current_ocf = current.get("operating_cashflow")
    current_profit = current.get("net_profit")

    if current_ocf is not None and current_profit is not None:
        if current_ocf < current_profit:
            risks.append("经营现金流低于净利润 → 利润质量偏弱")

    if revenue_yoy is not None and ar_yoy is not None:
        if ar_yoy > revenue_yoy + 10:
            risks.append("应收账款增长显著快于营收 → 回款风险")

    if revenue_yoy is not None and inventory_yoy is not None:
        if inventory_yoy > revenue_yoy + 10:
            risks.append("存货增长显著快于营收 → 库存积压风险")

    if revenue_yoy is not None and revenue_yoy < 0:
        risks.append("营收同比下滑 → 增长压力")

    if len(df) >= 3:
        ar_series = df["accounts_receivable"].dropna()
        inv_series = df["inventory"].dropna()

        if len(ar_series) >= 3:
            if ar_series.iloc[0] > ar_series.iloc[1] > ar_series.iloc[2]:
                memory_notes.append("应收账款连续两期上升（风险在累积）")

        if len(inv_series) >= 3:
            if inv_series.iloc[0] > inv_series.iloc[1] > inv_series.iloc[2]:
                memory_notes.append("存货连续两期上升（可能库存积压）")

    score = 100
    score -= len(risks) * 12
    score -= len(memory_notes) * 6
    score = max(0, min(100, score))

    if score >= 85:
        risk_level = "低风险"
    elif score >= 70:
        risk_level = "中低风险"
    elif score >= 55:
        risk_level = "中风险"
    elif score >= 40:
        risk_level = "中高风险"
    else:
        risk_level = "高风险"

    return {
        "company_name": ticker,
        "current_period": current.get("report_period", "未知"),
        "previous_period": previous.get("report_period", "未知"),
        "revenue_yoy": revenue_yoy,
        "profit_yoy": profit_yoy,
        "ar_yoy": ar_yoy,
        "inventory_yoy": inventory_yoy,
        "risks": risks,
        "memory_notes": memory_notes,
        "score": score,
        "risk_level": risk_level,
    }


# =========================
# 估值模块
# =========================
def get_valuation(info: dict, result: dict):
    pe = info.get("trailingPE", None)
    profit_margin = info.get("profitMargins", None)
    revenue_yoy = result.get("revenue_yoy", None)

    if pe is None:
        return {
            "valuation_label": "未知",
            "pe": None,
            "profit_margin": profit_margin,
            "valuation_reason": "暂无PE数据，无法完成估值判断。"
        }

    try:
        pe = float(pe)
    except Exception:
        return {
            "valuation_label": "未知",
            "pe": None,
            "profit_margin": profit_margin,
            "valuation_reason": "PE数据异常，无法完成估值判断。"
        }

    growth = revenue_yoy if revenue_yoy is not None else 0

    margin_pct = None
    if profit_margin is not None:
        try:
            margin_pct = round(float(profit_margin) * 100, 2)
        except Exception:
            margin_pct = None

    # PEG思维升级
    if pe >= 60:
        if growth >= 20:
            valuation_label = "高估值但有成长支撑"
            valuation_reason = f"当前PE为 {round(pe,2)}，估值处于高位，但营收同比达到 {growth}% ，市场给予较强成长预期。"
        else:
            valuation_label = "估值偏高"
            valuation_reason = f"当前PE为 {round(pe,2)}，估值较高，但营收同比仅为 {growth}% ，成长支撑不足。"

    elif pe >= 30:
        if growth >= 15:
            valuation_label = "估值合理偏高"
            valuation_reason = f"当前PE为 {round(pe,2)}，估值不低，但营收同比为 {growth}% ，说明估值有一定成长支撑。"
        else:
            valuation_label = "估值偏高"
            valuation_reason = f"当前PE为 {round(pe,2)}，估值偏高，而增长表现一般。"

    elif pe >= 15:
        if growth >= 10:
            valuation_label = "估值合理"
            valuation_reason = f"当前PE为 {round(pe,2)}，配合 {growth}% 的营收增长，整体估值相对合理。"
        else:
            valuation_label = "估值中性"
            valuation_reason = f"当前PE为 {round(pe,2)}，增长不突出，市场定价大体中性。"

    else:
        if growth > 0:
            valuation_label = "可能低估"
            valuation_reason = f"当前PE仅为 {round(pe,2)}，同时公司仍保持 {growth}% 的营收增长，可能存在低估。"
        else:
            valuation_label = "低估值但需谨慎"
            valuation_reason = f"当前PE仅为 {round(pe,2)}，估值不高，但增长表现偏弱，低估值未必意味着便宜。"

    return {
        "valuation_label": valuation_label,
        "pe": round(pe, 2),
        "profit_margin": margin_pct,
        "valuation_reason": valuation_reason,
    }


# =========================
# AI 分析
# =========================
def generate_ai_analysis(ticker: str, result: dict, valuation_label: str) -> str:
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return "AI分析失败：未检测到 DEEPSEEK_API_KEY，请先在终端设置环境变量。"

        url = "https://api.deepseek.com/v1/chat/completions"

        prompt = f"""
你是一名专业投资分析师，请基于以下信息，用简洁中文输出分析：

股票：{ticker}
营收同比：{result.get("revenue_yoy")}%
利润同比：{result.get("profit_yoy")}%
应收同比：{result.get("ar_yoy")}%
存货同比：{result.get("inventory_yoy")}%
风险等级：{result.get("risk_level")}
风险得分：{result.get("score")}
主要风险：{result.get("risks")}
趋势记忆：{result.get("memory_notes")}
估值判断：{valuation_label}

请输出四部分：
1. 公司经营情况
2. 当前主要风险
3. 估值解释
4. 是否值得继续关注（不要直接说买或卖）
"""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

        response = requests.post(url, headers=headers, json=data, timeout=60)
        res = response.json()

        if "choices" in res and len(res["choices"]) > 0:
            return res["choices"][0]["message"]["content"]

        return f"AI分析失败：接口返回异常 {res}"

    except Exception as e:
        return f"AI分析失败：{str(e)}"


# =========================
# 排行榜 / 推荐
# =========================
@st.cache_data(ttl=3600)
def rank_market(tickers):
    ranked = []

    for t in tickers:
        try:
            bundle = get_stock_bundle(t)
            financial_df = build_financial_df(bundle)
            result = analyze_financials(financial_df, t)
            if "error" not in result:
                ranked.append({
                    "ticker": t,
                    "score": result["score"],
                    "risk_level": result["risk_level"],
                    "revenue_yoy": result["revenue_yoy"],
                })
        except Exception:
            continue

    if not ranked:
        return pd.DataFrame()

    return pd.DataFrame(ranked).sort_values("score", ascending=False).reset_index(drop=True)


def pick_stocks(ranking_df: pd.DataFrame):
    if ranking_df.empty:
        return []

    picks = ranking_df.copy()
    picks = picks[picks["score"] >= 70]

    if "revenue_yoy" in picks.columns:
        picks = picks[picks["revenue_yoy"].fillna(-999) > 0]

    return picks["ticker"].head(3).tolist()


# =========================
# 状态初始化
# =========================
if "ticker" not in st.session_state:
    st.session_state.ticker = "AAPL"

if "compare_ticker" not in st.session_state:
    st.session_state.compare_ticker = ""

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = None

if "ai_result" not in st.session_state:
    st.session_state.ai_result = ""


# =========================
# 热门股票 & 排行榜
# =========================
st.subheader("🔥 热门股票")
hot_cols = st.columns(6)
hot_list = ["AAPL", "TSLA", "NVDA", "MSFT", "0700.HK", "600519.SS"]

for i, hot in enumerate(hot_list):
    if hot_cols[i].button(hot):
        st.session_state.ticker = hot

st.subheader("🏆 市场排行榜")
ranking_universe = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "0700.HK", "9988.HK"]
ranking_df = rank_market(ranking_universe)

if not ranking_df.empty:
    st.dataframe(ranking_df, use_container_width=True)
else:
    st.caption("排行榜数据加载中或当前不可用。")

st.subheader("💡 AI推荐股票")
picks = pick_stocks(ranking_df)
if picks:
    st.write("、".join(picks))
else:
    st.caption("当前暂无明显优先推荐标的。")


# =========================
# 输入区
# =========================
ticker = st.text_input(
    "请输入股票代码（如 AAPL / TSLA / PDD / 0700.HK / 600519.SS）",
    value=st.session_state.ticker,
).strip().upper()

compare_ticker = st.text_input(
    "对比股票（可选）",
    value=st.session_state.compare_ticker,
).strip().upper()

compare_period = st.selectbox(
    "对比区间",
    ["1mo", "3mo", "6mo", "1y", "5y"],
    index=3
)

benchmark = st.selectbox(
    "基准指数（Benchmark）",
    ["SPY", "QQQ", "DIA"],
    index=0
)

col1, col2 = st.columns(2)
with col1:
    run = st.button("🚀 一键分析")
with col2:
    generate_ai = st.button("🤖 生成AI报告")


# =========================
# 开始分析
# =========================
if run and ticker:
    st.session_state.ticker = ticker
    st.session_state.compare_ticker = compare_ticker
    st.session_state.ai_result = ""

    try:
        with st.spinner("正在获取数据..."):
            bundle = get_stock_bundle(ticker, history_period="1y")
            info = bundle["info"]
            history = bundle["history"]
            financial_df = build_financial_df(bundle)

        result = analyze_financials(financial_df, ticker)

        if "error" in result:
            st.session_state.analysis_done = False
            st.session_state.analysis_data = None
            st.error(result["error"])
        else:
            valuation_data = get_valuation(info, result)

            st.session_state.analysis_done = True
            st.session_state.analysis_data = {
                "ticker": ticker,
                "market": bundle["market"],
                "info": info,
                "history": history,
                "financial_df": financial_df,
                "result": result,
                "valuation_data": valuation_data,
                "compare_ticker": compare_ticker,
                "compare_period": compare_period,
                "benchmark": benchmark,
            }

    except Exception as e:
        st.session_state.analysis_done = False
        st.session_state.analysis_data = None
        st.error(f"出错了：{str(e)}")


# =========================
# AI 报告
# =========================
if generate_ai:
    if st.session_state.analysis_done and st.session_state.analysis_data:
        data = st.session_state.analysis_data
        with st.spinner("AI分析中..."):
            st.session_state.ai_result = generate_ai_analysis(
                data["ticker"],
                data["result"],
                data["valuation_data"]["valuation_label"]
            )
    else:
        st.warning("请先点击“一键分析”生成基础结果。")


# =========================
# 展示分析结果
# =========================
if st.session_state.analysis_done and st.session_state.analysis_data:
    data = st.session_state.analysis_data
    ticker = data["ticker"]
    market = data["market"]
    info = data["info"]
    history = data["history"]
    financial_df = data["financial_df"]
    result = data["result"]
    valuation_data = data["valuation_data"]
    compare_ticker = data["compare_ticker"]
    compare_period = data["compare_period"]
    benchmark = data["benchmark"]

    st.subheader("🌍 市场识别")
    st.write("识别市场：", market)

    if market == "美股":
        st.success("当前市场支持最佳：美股")
    elif market == "港股":
        st.info("当前市场支持中等：港股，部分财务字段可能缺失")
    else:
        st.warning("当前市场支持较弱：A股部分财务字段可能缺失，结果仅供参考")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("营收同比", f"{result['revenue_yoy']}%" if result["revenue_yoy"] is not None else "N/A")
    m2.metric("利润同比", f"{result['profit_yoy']}%" if result["profit_yoy"] is not None else "N/A")
    m3.metric("风险等级", result["risk_level"])
    m4.metric("估值判断", valuation_data["valuation_label"])

    st.subheader("📌 基本信息")
    st.write("股票代码：", ticker)
    st.write("公司名称：", info.get("longName", "未知"))
    st.write("行业：", info.get("industry", "未知"))
    st.write("当前期：", result["current_period"])
    st.write("上一期：", result["previous_period"])

    st.subheader("⚠️ 本期风险")
    if result["risks"]:
        for r in result["risks"]:
            st.write("-", r)
    else:
        st.success("暂无明显风险")

    st.subheader("🧠 趋势记忆")
    if result["memory_notes"]:
        for note in result["memory_notes"]:
            st.write("-", note)
    else:
        st.write("暂无持续恶化信号")

    st.subheader("📊 风险评分")
    st.write(result["score"], result["risk_level"])

    st.subheader("💰 估值分析")
    if valuation_data["pe"] is not None:
        st.write("PE：", valuation_data["pe"])
    else:
        st.write("PE：暂无数据")

    if valuation_data["profit_margin"] is not None:
        st.write("利润率：", f'{valuation_data["profit_margin"]}%')
    else:
        st.write("利润率：暂无数据")

    st.write("估值判断：", valuation_data["valuation_label"])
    st.info(valuation_data["valuation_reason"])

    st.subheader("📉 股价走势")
    if not history.empty and "Close" in history.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=history.index, y=history["Close"], mode="lines", name=ticker))
        fig.update_layout(template="plotly_dark", height=420)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("暂无股价走势数据")

    st.subheader("📊 营收趋势")
    if not financial_df.empty and "revenue" in financial_df.columns:
        revenue_df = financial_df[["report_period", "revenue"]].dropna().sort_values("report_period")
        if not revenue_df.empty:
            revenue_df["revenue_billion"] = revenue_df["revenue"] / 1e9
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=revenue_df["report_period"],
                y=revenue_df["revenue_billion"],
                name="Revenue (Billion)"
            ))
            fig2.update_layout(template="plotly_dark", height=400)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("暂无营收趋势数据")
    else:
        st.warning("暂无营收趋势数据")

    # =========================
    # Bloomberg 终端级对比模块
    # =========================
    if compare_ticker:
        st.subheader("🆚 股票对比（终端级）")

        try:
            main_hist = yf.Ticker(ticker).history(period=compare_period)
            comp_hist = yf.Ticker(compare_ticker).history(period=compare_period)
            bench_hist = yf.Ticker(benchmark).history(period=compare_period)

            if (
                not main_hist.empty
                and not comp_hist.empty
                and "Close" in main_hist.columns
                and "Close" in comp_hist.columns
            ):
                df1 = main_hist[["Close", "Volume"]].rename(columns={"Close": ticker, "Volume": f"{ticker}_Volume"})
                df2 = comp_hist[["Close", "Volume"]].rename(columns={"Close": compare_ticker, "Volume": f"{compare_ticker}_Volume"})

                compare_df = pd.concat([df1, df2], axis=1)
                compare_df = compare_df.sort_index().ffill().bfill().dropna(how="all")

                if compare_df.empty:
                    st.warning("⚠️ 对比数据为空")
                else:
                    price_df = compare_df[[ticker, compare_ticker]].copy()
                    normalized_df = price_df / price_df.iloc[0] * 100

                    fig_compare = make_subplots(
                        rows=2,
                        cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.08,
                        row_heights=[0.7, 0.3],
                        subplot_titles=("归一化收益对比（起点=100）", "成交量")
                    )

                    for col in normalized_df.columns:
                        fig_compare.add_trace(
                            go.Scatter(
                                x=normalized_df.index,
                                y=normalized_df[col],
                                mode="lines",
                                name=col
                            ),
                            row=1,
                            col=1
                        )

                    fig_compare.add_trace(
                        go.Bar(
                            x=compare_df.index,
                            y=compare_df[f"{ticker}_Volume"],
                            name=f"{ticker} Volume",
                            opacity=0.5
                        ),
                        row=2,
                        col=1
                    )

                    fig_compare.add_trace(
                        go.Bar(
                            x=compare_df.index,
                            y=compare_df[f"{compare_ticker}_Volume"],
                            name=f"{compare_ticker} Volume",
                            opacity=0.5
                        ),
                        row=2,
                        col=1
                    )

                    fig_compare.update_layout(
                        template="plotly_dark",
                        height=780,
                        barmode="overlay",
                        xaxis_title="日期",
                        yaxis_title="收益指数",
                        yaxis2_title="成交量"
                    )

                    st.plotly_chart(fig_compare, use_container_width=True)

                    st.subheader("📉 回撤曲线")
                    returns = price_df.pct_change().dropna()
                    cumulative = (1 + returns).cumprod()
                    rolling_max = cumulative.cummax()
                    drawdown_df = cumulative / rolling_max - 1

                    fig_dd = go.Figure()
                    for col in drawdown_df.columns:
                        fig_dd.add_trace(go.Scatter(
                            x=drawdown_df.index,
                            y=drawdown_df[col],
                            mode="lines",
                            name=col
                        ))

                    fig_dd.update_layout(
                        template="plotly_dark",
                        height=400,
                        title="最大回撤走势",
                        xaxis_title="日期",
                        yaxis_title="回撤"
                    )
                    st.plotly_chart(fig_dd, use_container_width=True)

                    st.subheader("📊 风险收益指标")
                    metrics = []

                    benchmark_returns = bench_hist["Close"].pct_change().dropna() if not bench_hist.empty and "Close" in bench_hist.columns else pd.Series(dtype=float)

                    for col in price_df.columns:
                        series = price_df[col].dropna()
                        ret = returns[col].dropna()

                        if len(series) < 2 or len(ret) < 2:
                            continue

                        total_return = series.iloc[-1] / series.iloc[0] - 1
                        annual_return = (1 + total_return) ** (252 / len(series)) - 1
                        annual_vol = ret.std() * (252 ** 0.5)
                        sharpe = annual_return / annual_vol if annual_vol != 0 else None

                        cum = (1 + ret).cumprod()
                        roll_max = cum.cummax()
                        dd = cum / roll_max - 1
                        max_dd = dd.min()

                        # Beta
                        beta = None
                        if not benchmark_returns.empty:
                            aligned = pd.concat([ret, benchmark_returns], axis=1).dropna()
                            aligned.columns = ["asset", "market"]
                            if len(aligned) > 2 and aligned["market"].var() != 0:
                                beta = aligned["asset"].cov(aligned["market"]) / aligned["market"].var()

                        # Alpha（简化）
                        alpha = None
                        if beta is not None:
                            market_ann = (1 + benchmark_returns.mean()) ** 252 - 1 if len(benchmark_returns) > 0 else 0
                            alpha = annual_return - beta * market_ann

                        metrics.append({
                            "股票": col,
                            "累计收益": f"{round(total_return * 100, 2)}%",
                            "年化收益": f"{round(annual_return * 100, 2)}%",
                            "年化波动": f"{round(annual_vol * 100, 2)}%",
                            "最大回撤": f"{round(max_dd * 100, 2)}%",
                            "夏普比率": round(sharpe, 2) if sharpe is not None else "N/A",
                            "Beta": round(beta, 2) if beta is not None else "N/A",
                            "Alpha": round(alpha, 4) if alpha is not None else "N/A",
                        })

                    metrics_df = pd.DataFrame(metrics)
                    st.dataframe(metrics_df, use_container_width=True)

                    if len(metrics_df) >= 2:
                        st.subheader("🏁 自动结论")
                        try:
                            temp_df = metrics_df.copy()
                            temp_df["累计收益_num"] = temp_df["累计收益"].str.replace("%", "").astype(float)
                            temp_df["年化收益_num"] = temp_df["年化收益"].str.replace("%", "").astype(float)
                            temp_df["最大回撤_num"] = temp_df["最大回撤"].str.replace("%", "").astype(float)
                            temp_df["夏普比率_num"] = temp_df["夏普比率"].replace("N/A", float("-inf")).astype(float)

                            best_return = temp_df.loc[temp_df["累计收益_num"].idxmax(), "股票"]
                            best_sharpe = temp_df.loc[temp_df["夏普比率_num"].idxmax(), "股票"]
                            best_drawdown = temp_df.loc[temp_df["最大回撤_num"].idxmax(), "股票"]

                            st.write(f"📈 收益表现更强：**{best_return}**")
                            st.write(f"⚖️ 风险调整后收益更优：**{best_sharpe}**")
                            st.write(f"🛡️ 回撤控制更好：**{best_drawdown}**")
                        except Exception:
                            st.caption("自动结论生成失败，但上方指标仍可参考。")

            else:
                st.warning("⚠️ 对比股票暂无有效历史价格数据")

        except Exception as e:
            st.error(f"❌ 股票对比失败：{str(e)}")

    st.subheader("🤖 AI总结")
    simple_summary = f"""
公司当前营收同比 {result['revenue_yoy']}%，利润同比 {result['profit_yoy']}%，应收同比 {result['ar_yoy']}%，存货同比 {result['inventory_yoy']}%。
综合来看，风险等级为【{result['risk_level']}】，当前估值判断为【{valuation_data["valuation_label"]}】。
"""
    st.info(simple_summary)

    st.subheader("🧠 AI深度分析")
    if st.session_state.ai_result:
        st.write(st.session_state.ai_result)
    else:
        st.caption("点击上方“🤖 生成AI报告”后，这里会显示详细分析。")