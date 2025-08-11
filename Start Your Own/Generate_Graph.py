"""Plot ChatGPT portfolio performance against the S&P 500.

The script loads logged portfolio equity, fetches S&P 500 data, and
renders a comparison chart. Core behaviour remains unchanged; the code
is simply reorganised and commented for clarity.
"""

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
PORTFOLIO_CSV = str(DATA_DIR / "chatgpt_portfolio_update.csv")


def load_portfolio_totals() -> pd.DataFrame:
    """Load portfolio equity history including a baseline row."""
    chatgpt_df = pd.read_csv(PORTFOLIO_CSV)
    chatgpt_totals = chatgpt_df[chatgpt_df["Ticker"] == "TOTAL"].copy()
    chatgpt_totals["Date"] = pd.to_datetime(chatgpt_totals["Date"])

    baseline_date = pd.Timestamp("2025-06-27")
    baseline_equity = 100
    baseline_row = pd.DataFrame({"Date": [baseline_date], "Total Equity": [baseline_equity]})
    return pd.concat([baseline_row, chatgpt_totals], ignore_index=True).sort_values("Date")


def download_sp500(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    sp500 = yf.download("^SPX", start=start_date, end=end_date + pd.Timedelta(days=1), progress=False)
    if sp500 is None or len(sp500) == 0:
        sp500 = yf.download("^GSPC", start=start_date, end=end_date + pd.Timedelta(days=1), progress=False)
    if sp500 is None or len(sp500) == 0:
        sp500 = yf.download("SPY", start=start_date, end=end_date + pd.Timedelta(days=1), progress=False)
    sp500 = sp500 if sp500 is not None else pd.DataFrame()
    sp500 = sp500.reset_index()
    if isinstance(sp500.columns, pd.MultiIndex):
        sp500.columns = sp500.columns.get_level_values(0)
    if "Close" not in sp500 or len(sp500["Close"]) == 0:
        return pd.DataFrame(columns=["Date", "SPX Value ($100 Invested)"])
    base_close = float(sp500["Close"].iloc[0]) if float(sp500["Close"].iloc[0]) != 0 else 1.0
    scaling_factor = 100 / base_close
    sp500["SPX Value ($100 Invested)"] = sp500["Close"] * scaling_factor
    return sp500


def main() -> None:
    """Generate and display the comparison graph."""
    chatgpt_totals = load_portfolio_totals()

    start_date = pd.Timestamp("2025-06-27")
    end_date = chatgpt_totals["Date"].max()
    sp500 = download_sp500(start_date, end_date)

    plt.figure(figsize=(10, 6))
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.plot(
        chatgpt_totals["Date"],
        chatgpt_totals["Total Equity"],
        label="ChatGPT ($100 Invested)",
        marker="o",
        color="blue",
        linewidth=2,
    )
    if not sp500.empty:
        plt.plot(
            sp500["Date"],
            sp500["SPX Value ($100 Invested)"],
            label="S&P 500 ($100 Invested)",
            marker="o",
            color="orange",
            linestyle="--",
            linewidth=2,
        )

    final_date = chatgpt_totals["Date"].iloc[-1]
    final_chatgpt = float(chatgpt_totals["Total Equity"].iloc[-1])
    plt.text(final_date, final_chatgpt + 0.3, f"+{final_chatgpt - 100:.1f}%", color="blue", fontsize=9)
    if not sp500.empty:
        final_spx = float(sp500["SPX Value ($100 Invested)"].iloc[-1])
        plt.text(final_date, final_spx + 0.9, f"+{final_spx - 100:.1f}%", color="orange", fontsize=9)

    drawdown_date = pd.Timestamp("2025-07-11")
    drawdown_value = 102.46
    plt.text(drawdown_date + pd.Timedelta(days=0.5), drawdown_value - 0.5, "-7% Drawdown", color="red", fontsize=9)
    plt.title("ChatGPT's Micro Cap Portfolio vs. S&P 500")
    plt.xlabel("Date")
    plt.ylabel("Value of $100 Investment")
    plt.xticks(rotation=15)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

