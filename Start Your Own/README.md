# Start Your Own

This folder lets you run the trading experiment on your own computer. It now supports three modes:
- dry-run (default): CSV/yfinance only, no orders submitted
- paper: submits orders to a broker paper account (Alpaca)
- live: submits live orders with guard rails

Data and logs are saved inside this folder.

## Quick Start (dry-run)

1) Install Python packages
   ```bash
   pip install -r requirements.txt
   ```

2) Run the original script
   ```bash
   python "Start Your Own/Trading_Script.py"
   ```

3) Follow the prompts
   - The program uses past data from 'chatgpt_portfolio_update.csv' to automatically grab today's portfolio.
   - If it is a weekend, the script will inform you that date will be inaccurate. However, this is easily fixable by editing CSV files manually and saving.
   - If 'chatgpt_portfolio_update.csv' is empty (meaning no past trading days logged), you will be required to enter your starting cash.
   - From here, you can set up your portfolio or make any changes.
   - The script asks if you want to record manual buys or sells.
   - After you hit 'Enter' all calculations for the day are made.
   - Results are saved to `chatgpt_portfolio_update.csv` and any trades are added to `chatgpt_trade_log.csv`.

## Paper/Live Trading (Alpaca)

1) Copy and edit .env
   ```bash
   cp .env.example .env
   # fill in ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY
   # set MODE=paper (or live)
   ```

2) Create a simple plan file of desired orders (optional)
   ```bash
   cp examples/plan.json my_plan.json
   ```

3) Submit in paper mode with confirmation
   ```bash
   python start_trading.py --mode paper --plan-file my_plan.json --confirm
   ```

Notes:
- MODE can also be set via environment variable, e.g. `MODE=paper`.
- Risk guardrails are configurable in .env (see RISK_* variables).
- Live trading requires MODE=live and valid credentials; start with tiny notionals.

## Generate_Graph.py

This script draws a graph of your portfolio versus the S&P 500.

1) Ensure you have portfolio data
   - Run `Trading_Script.py` at least once so `chatgpt_portfolio_update.csv` has data.
2) Run the graph script
   ```bash
   python "Start Your Own/Generate_Graph.py" --baseline-equity 100
   ```
   - Optional flags `--start-date` and `--end-date` accept dates in `YYYY-MM-DD` format. For example:
   ```bash
   python "Start Your Own/Generate_Graph.py" --baseline-equity 100 --start-date 2023-01-01 --end-date 2023-12-31
   ```
3) View the chart
   - A window opens showing your portfolio value vs. S&P 500. Results will be adjusted for baseline equity.

All of this is still very new, so there may be bugs. Please reach out if you find an issue or have a question.
