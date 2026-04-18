def analyze_financials(company_df, company_name="A公司"):
    # ===== 检查数据是否为空 =====
    if company_df.empty:
        return {
            "error": f"没有找到公司：{company_name}"
        }

    # ===== 排序 =====
    company_df = company_df.sort_values("report_period")

    if len(company_df) < 2:
        return {
            "error": "数据不足（至少需要2期）"
        }

    # ===== 取最近两期 =====
    previous = company_df.iloc[-2]
    current = company_df.iloc[-1]

    # ===== 计算同比 =====
    def growth_rate(curr, prev):
        if prev == 0:
            return 0
        return (curr - prev) / prev

    revenue_yoy = growth_rate(current["revenue"], previous["revenue"])
    ar_yoy = growth_rate(current["accounts_receivable"], previous["accounts_receivable"])
    inventory_yoy = growth_rate(current["inventory"], previous["inventory"])

    # ===== 风险判断 =====
    risks = []

    if revenue_yoy > 0.3 and ar_yoy > revenue_yoy:
        risks.append("应收账款增长快于营收 → 回款风险")

    if current["operating_cashflow"] < current["net_profit"]:
        risks.append("经营现金流低于净利润 → 利润质量偏弱")

    if inventory_yoy > revenue_yoy:
        risks.append("存货增长快于营收 → 库存积压风险")

    # ===== 记忆（趋势分析）=====
    memory_notes = []

    if len(company_df) >= 3:
        third = company_df.iloc[-3]

        if third["accounts_receivable"] < previous["accounts_receivable"] < current["accounts_receivable"]:
            memory_notes.append("应收账款连续两期上升（风险在累积）")

        if third["inventory"] < previous["inventory"] < current["inventory"]:
            memory_notes.append("存货连续两期上升（库存压力增加）")

        if (
            previous["operating_cashflow"] < previous["net_profit"]
            and current["operating_cashflow"] < current["net_profit"]
        ):
            memory_notes.append("经营现金流连续两期弱于利润（问题持续）")

    # ===== 风险评分 =====
    score = 100
    score -= len(risks) * 10
    score -= len(memory_notes) * 5

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

    # ===== 返回结果（不给print，交给网页显示）=====
    return {
        "company_name": current["company_name"],
        "current_period": current["report_period"],
        "previous_period": previous["report_period"],
        "revenue_yoy": round(revenue_yoy * 100, 2),
        "ar_yoy": round(ar_yoy * 100, 2),
        "inventory_yoy": round(inventory_yoy * 100, 2),
        "risks": risks,
        "memory_notes": memory_notes,
        "score": score,
        "risk_level": risk_level
    }