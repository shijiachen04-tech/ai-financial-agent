import pandas as pd
import yfinance as yf


def detect_market(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if ticker.endswith(".HK"):
        return "港股"
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "A股"
    return "美股"


def safe_to_number(x, default=0.0):
    try:
        if x is None:
            return default
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def safe_date(x):
    try:
        return str(x.date()) if hasattr(x, "date") else str(x)
    except Exception:
        return str(x)


def first_existing(series_or_dict, candidates, default=0.0):
    for name in candidates:
        try:
            if name in series_or_dict:
                value = series_or_dict.get(name)
                if pd.notna(value):
                    return safe_to_number(value, default)
        except Exception:
            continue
    return default


def get_stock_bundle(ticker: str, history_period: str = "1y"):
    stock = yf.Ticker(ticker)

    try:
        info = stock.info if stock.info else {}
    except Exception:
        info = {}

    try:
        history = stock.history(period=history_period)
        if history is None:
            history = pd.DataFrame()
    except Exception:
        history = pd.DataFrame()

    try:
        financials = stock.financials.T if stock.financials is not None else pd.DataFrame()
        if financials is None:
            financials = pd.DataFrame()
    except Exception:
        financials = pd.DataFrame()

    try:
        balance = stock.balance_sheet.T if stock.balance_sheet is not None else pd.DataFrame()
        if balance is None:
            balance = pd.DataFrame()
    except Exception:
        balance = pd.DataFrame()

    try:
        cashflow = stock.cashflow.T if stock.cashflow is not None else pd.DataFrame()
        if cashflow is None:
            cashflow = pd.DataFrame()
    except Exception:
        cashflow = pd.DataFrame()

    return {
        "ticker": ticker,
        "market": detect_market(ticker),
        "info": info,
        "history": history,
        "financials": financials,
        "balance": balance,
        "cashflow": cashflow,
    }


def build_financial_df(bundle: dict) -> pd.DataFrame:
    ticker = bundle["ticker"]
    financials = bundle["financials"]
    balance = bundle["balance"]
    cashflow = bundle["cashflow"]

    if financials is None or financials.empty:
        return pd.DataFrame(columns=[
            "company_name",
            "report_period",
            "revenue",
            "net_profit",
            "operating_cashflow",
            "accounts_receivable",
            "inventory",
        ])

    rows = []

    for date in financials.index:
        fin_row = financials.loc[date] if date in financials.index else pd.Series(dtype="object")
        bal_row = balance.loc[date] if date in balance.index else pd.Series(dtype="object")
        cf_row = cashflow.loc[date] if date in cashflow.index else pd.Series(dtype="object")

        revenue = first_existing(
            fin_row,
            ["Total Revenue", "Revenue", "Operating Revenue"],
            default=0.0,
        )

        net_profit = first_existing(
            fin_row,
            ["Net Income", "Net Income Common Stockholders", "Net Profit"],
            default=0.0,
        )

        operating_cashflow = first_existing(
            cf_row,
            ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
            default=0.0,
        )

        accounts_receivable = first_existing(
            bal_row,
            ["Accounts Receivable", "Receivables", "Accounts Notes Receivable"],
            default=0.0,
        )

        inventory = first_existing(
            bal_row,
            ["Inventory", "Inventories"],
            default=0.0,
        )

        rows.append({
            "company_name": ticker,
            "report_period": safe_date(date),
            "revenue": revenue,
            "net_profit": net_profit,
            "operating_cashflow": operating_cashflow,
            "accounts_receivable": accounts_receivable,
            "inventory": inventory,
        })

    df = pd.DataFrame(rows)

    numeric_cols = [
        "revenue",
        "net_profit",
        "operating_cashflow",
        "accounts_receivable",
        "inventory",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df.sort_values("report_period", ascending=False).reset_index(drop=True)

    return df


def get_revenue_chart_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "revenue" not in df.columns:
        return pd.DataFrame(columns=["report_period", "revenue_billion"])

    chart_df = df[["report_period", "revenue"]].copy()
    chart_df["revenue"] = pd.to_numeric(chart_df["revenue"], errors="coerce").fillna(0.0)
    chart_df = chart_df.sort_values("report_period")

    chart_df["revenue_billion"] = chart_df["revenue"] / 1e9

    return chart_df[["report_period", "revenue_billion"]]


def get_profit_chart_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "net_profit" not in df.columns:
        return pd.DataFrame(columns=["report_period", "profit_billion"])

    chart_df = df[["report_period", "net_profit"]].copy()
    chart_df["net_profit"] = pd.to_numeric(chart_df["net_profit"], errors="coerce").fillna(0.0)
    chart_df = chart_df.sort_values("report_period")

    chart_df["profit_billion"] = chart_df["net_profit"] / 1e9

    return chart_df[["report_period", "profit_billion"]]