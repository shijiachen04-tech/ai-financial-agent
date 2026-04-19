import pandas as pd


def calc_yoy(current, previous):
    try:
        if current is None or previous is None or pd.isna(current) or pd.isna(previous):
            return None
        if previous == 0:
            return None
        return round((current - previous) / abs(previous) * 100, 2)
    except Exception:
        return None


def compare_two_periods(df: pd.DataFrame):
    if df is None or df.empty or len(df) < 2:
        return None, None

    current = df.iloc[0]
    previous = df.iloc[1]
    return current, previous


def analyze_financials(df: pd.DataFrame, ticker: str) -> dict:
    if df is None or df.empty:
        return {"error": "无法获取有效财报数据"}

    current, previous = compare_two_periods(df)
    if current is None or previous is None:
        return {"error": "财报期数不足，至少需要两期"}

    revenue_yoy = calc_yoy(current.get("revenue"), previous.get("revenue"))
    ar_yoy = calc_yoy(current.get("accounts_receivable"), previous.get("accounts_receivable"))
    inventory_yoy = calc_yoy(current.get("inventory"), previous.get("inventory"))

    risks = []
    memory_notes = []

    current_ocf = current.get("operating_cashflow")
    current_profit = current.get("net_profit")

    if pd.notna(current_ocf) and pd.notna(current_profit):
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
    score -= len(risks) * 10
    score -= len(memory_notes) * 5
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
        "ar_yoy": ar_yoy,
        "inventory_yoy": inventory_yoy,
        "risks": risks,
        "memory_notes": memory_notes,
        "score": score,
        "risk_level": risk_level,
    }