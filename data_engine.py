import pandas as pd
import yfinance as yf


def detect_market(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if ticker.endswith(".HK"):
        return "港股"
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "A股"
    return "美股"


def safe_to_number(x):
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def first_existing(series_or_dict, candidates, default=None):
    for name in candidates:
        if name in series_or_dict:
            value = series_or_dict.get(name)
            if pd.notna(value):
                return value
    return default


def normalize_date(x):
    try:
        if hasattr(x, "date"):
            return str(x.date())
        return str(x)
    except Exception:
        return str(x)


def get_stock_bundle(ticker: str):
    stock = yf.Ticker(ticker)

    info = stock.info if stock.info else {}
    history = stock.history(period="1y")

    financials = stock.financials.T if stock.financials is not None else pd.DataFrame()
    balance = stock.balance_sheet.T if stock.balance_sheet is not None else pd.DataFrame()
    cashflow = stock.cashflow.T if stock.cashflow is not None else pd.DataFrame()

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

    if financials.empty:
        return pd.DataFrame()

    rows = []

    for date in financials.index:
        fin_row = financials.loc[date] if date in financials.index else pd.Series(dtype="object")
        bal_row = balance.loc[date] if date in balance.index else pd.Series(dtype="object")
        cf_row = cashflow.loc[date] if date in cashflow.index else pd.Series(dtype="object")

        revenue = first_existing(
            fin_row,
            ["Total Revenue", "Revenue", "Operating Revenue"],
            default=None,
        )

        net_profit = first_existing(
            fin_row,
            ["Net Income", "Net Income Common Stockholders", "Net Profit"],
            default=None,
        )

        operating_cashflow = first_existing(
            cf_row,
            ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
            default=None,
        )

        accounts_receivable = first_existing(
            bal_row,
            ["Accounts Receivable", "Receivables", "Accounts Notes Receivable"],
            default=None,
        )

        inventory = first_existing(
            bal_row,
            ["Inventory", "Inventories"],
            default=None,
        )

        rows.append({
            "company_name": ticker,
            "report_period": normalize_date(date),
            "revenue": safe_to_number(revenue),
            "net_profit": safe_to_number(net_profit),
            "operating_cashflow": safe_to_number(operating_cashflow),
            "accounts_receivable": safe_to_number(accounts_receivable),
            "inventory": safe_to_number(inventory),
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
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("report_period", ascending=False).reset_index(drop=True)


def get_revenue_chart_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "revenue" not in df.columns:
        return pd.DataFrame()

    chart_df = df[["report_period", "revenue"]].copy()
    chart_df = chart_df.dropna(subset=["revenue"])
    chart_df = chart_df.sort_values("report_period")

    if chart_df.empty:
        return pd.DataFrame()

    chart_df["revenue_billion"] = chart_df["revenue"] / 1e9
    return chart_df[["report_period", "revenue_billion"]]