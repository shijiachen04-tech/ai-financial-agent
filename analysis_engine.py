import pandas as pd


def safe_pct(value):
    try:
        if value is None:
            return 0.0
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    except Exception:
        return 0.0


def calc_yoy(current, previous):
    try:
        if current is None or previous is None:
            return 0.0
        if pd.isna(current) or pd.isna(previous):
            return 0.0
        if previous == 0:
            return 0.0
        return round((current - previous) / abs(previous) * 100, 2)
    except Exception:
        return 0.0


def analyze_financials(df: pd.DataFrame, ticker: str) -> dict:
    if df is None or df.empty:
        return {
            "company_name": ticker,
            "current_period": "未知",
            "previous_period": "未知",
            "revenue_yoy": 0.0,
            "profit_yoy": 0.0,
            "ar_yoy": 0.0,
            "inventory_yoy": 0.0,
            "risks": ["财报数据缺失"],
            "memory_notes": [],
            "score": 40,
            "risk_level": "中高风险",
        }

    df = df.copy()

    needed_cols = [
        "revenue",
        "net_profit",
        "operating_cashflow",
        "accounts_receivable",
        "inventory",
    ]

    for col in needed_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df.sort_values("report_period", ascending=False).reset_index(drop=True)

    current = df.iloc[0]
    previous = df.iloc[1] if len(df) > 1 else df.iloc[0]

    revenue_yoy = calc_yoy(current.get("revenue", 0.0), previous.get("revenue", 0.0))
    profit_yoy = calc_yoy(current.get("net_profit", 0.0), previous.get("net_profit", 0.0))
    ar_yoy = calc_yoy(current.get("accounts_receivable", 0.0), previous.get("accounts_receivable", 0.0))
    inventory_yoy = calc_yoy(current.get("inventory", 0.0), previous.get("inventory", 0.0))

    risks = []
    memory_notes = []
    score = 100

    # ===== 数据缺失惩罚（关键，防止“没数据但高分”）=====
    missing_penalty = 0

    if current.get("revenue", 0.0) == 0.0:
        missing_penalty += 10
        risks.append("营收数据缺失或不可用")

    if current.get("net_profit", 0.0) == 0.0:
        missing_penalty += 8
        risks.append("利润数据缺失或不可用")

    if current.get("accounts_receivable", 0.0) == 0.0:
        missing_penalty += 5

    if current.get("inventory", 0.0) == 0.0:
        missing_penalty += 5

    score -= missing_penalty

    # ===== 经营质量风险 =====
    current_ocf = current.get("operating_cashflow", 0.0)
    current_profit = current.get("net_profit", 0.0)

    if current_ocf < current_profit and current_profit != 0:
        risks.append("经营现金流低于净利润 → 利润质量偏弱")
        score -= 12

    # ===== 增长质量风险 =====
    if ar_yoy > revenue_yoy + 10 and ar_yoy != 0:
        risks.append("应收账款增长显著快于营收 → 回款风险")
        score -= 12

    if inventory_yoy > revenue_yoy + 10 and inventory_yoy != 0:
        risks.append("存货增长显著快于营收 → 库存积压风险")
        score -= 12

    if revenue_yoy < 0:
        risks.append("营收同比下滑 → 增长压力")
        score -= 10

    if profit_yoy < 0:
        risks.append("利润同比下滑 → 盈利承压")
        score -= 8

    # ===== 趋势记忆 =====
    if len(df) >= 3:
        ar_series = df["accounts_receivable"]
        inv_series = df["inventory"]
        revenue_series = df["revenue"]

        try:
            if ar_series.iloc[0] > ar_series.iloc[1] > ar_series.iloc[2] and ar_series.iloc[0] != 0:
                memory_notes.append("应收账款连续两期上升（风险在累积）")
                score -= 6
        except Exception:
            pass

        try:
            if inv_series.iloc[0] > inv_series.iloc[1] > inv_series.iloc[2] and inv_series.iloc[0] != 0:
                memory_notes.append("存货连续两期上升（可能库存积压）")
                score -= 6
        except Exception:
            pass

        try:
            if revenue_series.iloc[0] < revenue_series.iloc[1] < revenue_series.iloc[2] and revenue_series.iloc[0] != 0:
                memory_notes.append("营收连续两期下滑（增长趋势转弱）")
                score -= 8
        except Exception:
            pass

    # ===== 限制范围 =====
    score = max(0, min(100, int(round(score))))

    # ===== 风险等级 =====
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
        "revenue_yoy": safe_pct(revenue_yoy),
        "profit_yoy": safe_pct(profit_yoy),
        "ar_yoy": safe_pct(ar_yoy),
        "inventory_yoy": safe_pct(inventory_yoy),
        "risks": risks,
        "memory_notes": memory_notes,
        "score": score,
        "risk_level": risk_level,
    }