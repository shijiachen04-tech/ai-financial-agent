import streamlit as st
import pandas as pd
import yfinance as yf
from analysis_engine import analyze_financials

# ===== 页面标题 =====
st.title("📊 AI 财报风险分析系统（专业版）")

# ===== 合规免责声明 =====
st.warning("⚠️ 本工具仅用于学习与信息参考，不构成任何投资建议。投资有风险，请谨慎决策。")

# ===== 输入股票代码 =====
ticker = st.text_input("请输入公司股票代码（如 AAPL / TSLA）", "AAPL")

if ticker:
    try:
        stock = yf.Ticker(ticker)

        # ===== 获取财报 =====
        income = stock.financials.T
        balance = stock.balance_sheet.T
        cashflow = stock.cashflow.T

        if income.empty or balance.empty or cashflow.empty:
            st.error("无法获取完整财务数据，请尝试其他股票代码。")
        else:
            rows = []

            # ===== 拼接统一数据结构 =====
            for date in income.index:
                row = {
                    "company_name": ticker,
                    "report_period": str(date.date()),
                    "revenue": income.loc[date].get("Total Revenue", 0),
                    "net_profit": income.loc[date].get("Net Income", 0),
                    "operating_cashflow": cashflow.loc[date].get("Operating Cash Flow", 0),
                    "accounts_receivable": balance.loc[date].get("Accounts Receivable", 0),
                    "inventory": balance.loc[date].get("Inventory", 0),
                }
                rows.append(row)

            df = pd.DataFrame(rows)

            # ===== 调用分析引擎 =====
            result = analyze_financials(df, ticker)

            if "error" in result:
                st.error(result["error"])

            else:
                # ===== 基本信息 =====
                st.subheader("📌 基本信息")
                st.write("公司代码：", result["company_name"])
                st.write("当前期：", result["current_period"])
                st.write("上一期：", result["previous_period"])

                # ===== 指标变化 =====
                st.subheader("📈 指标变化")
                st.write("营收同比：", result["revenue_yoy"], "%")
                st.write("应收同比：", result["ar_yoy"], "%")
                st.write("存货同比：", result["inventory_yoy"], "%")

                # ===== 本期风险 =====
                st.subheader("⚠️ 本期风险")
                if not result["risks"]:
                    st.success("暂无明显风险")
                else:
                    for r in result["risks"]:
                        st.write("-", r)

                # ===== 趋势记忆 =====
                st.subheader("🧠 趋势记忆")
                if not result["memory_notes"]:
                    st.write("暂无持续恶化信号")
                else:
                    for note in result["memory_notes"]:
                        st.write("-", note)

                # ===== 风险评分 =====
                st.subheader("📊 风险评分")
                st.write("风险得分：", result["score"])
                st.write("风险等级：", result["risk_level"])

                # ===== 估值分析 =====
                st.subheader("💰 估值分析")

                info = stock.info
                pe = info.get("trailingPE", None)

                if pe:
                    st.write("市盈率（PE）：", round(pe, 2))
                else:
                    st.write("市盈率：暂无数据")

                growth = result["revenue_yoy"]
                valuation = "未知"

                if pe:
                    if pe < 15 and growth > 10:
                        valuation = "🟢 估值偏低"
                    elif pe < 25:
                        valuation = "🟡 估值合理"
                    elif pe < 40:
                        valuation = "🟠 估值偏高"
                    else:
                        valuation = "🔴 估值较高"

                st.write("估值判断：", valuation)

                # ===== 投资结论 =====
                st.subheader("📌 投资结论")

                score = result["score"]

                if score >= 85:
                    st.success("🟢 公司整体财务健康，风险较低，可作为关注标的（仅供参考）")
                elif score >= 70:
                    st.info("🟡 公司风险可控，建议持续跟踪关键指标变化")
                elif score >= 55:
                    st.warning("🟠 公司存在一定风险，建议谨慎评估")
                elif score >= 40:
                    st.warning("🔴 公司风险较高，建议观望")
                else:
                    st.error("⚫ 公司风险较大，不建议关注")

                # ===== 风险解释 =====
                if result["risks"]:
                    st.write("📎 主要风险来源：")
                    for r in result["risks"]:
                        st.write("-", r)

                if result["memory_notes"]:
                    st.write("📎 趋势提示：")
                    for note in result["memory_notes"]:
                        st.write("-", note)

                # ===== AI总结 =====
                st.subheader("🤖 AI总结")

                summary = f"""
该公司当前营收同比 {result['revenue_yoy']}%，应收账款同比 {result['ar_yoy']}%，存货同比 {result['inventory_yoy']}%。
综合来看，公司风险等级为【{result['risk_level']}】，当前估值判断为【{valuation}】。
"""

                st.info(summary)

    except Exception as e:
        st.error("出错了：" + str(e))