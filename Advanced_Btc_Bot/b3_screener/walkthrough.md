# B3 Screener Dashboard 🇧🇷

A modular command-line tool that provides a complete snapshot of the Brazilian market, including Macro Indicators, Stocks, FIIs, and ETFs.

## How to Run

1.  **Open your terminal** in the project folder:
    `E:\acao\b3_screener`

2.  **Run the dashboard**:
    ```bash
    node index.js
    ```

## Features

### 1. Macro Indicators 💵
Displays the real-time **USD/BRL** exchange rate and the current **Selic Rate** at the top of the dashboard.

### 2. Stocks Screener 🏢
Filters for the best "Value Investing" opportunities:
*   **Graham Formula**: Shows Fair Price and Upside.
*   **Debt Filter**: Filters out companies with Net Debt > Equity.
*   **Dividends**: Yield > 6%.
*   **P/VP**: 0 < P/VP < 1.2.

### 3. FIIs Screener 🏘️ (New!)
Filters for the best Real Estate Funds:
*   **P/VP**: 0.4 - 1.2 (Fair Price).
*   **Dividend Yield**: > 6%.
*   **Physical Vacancy**: < 15% (Avoids funds with many empty properties).
*   **Liquidity**: > R$ 50k daily.

### 4. ETFs 📊
Lists popular ETFs for diversification (IVVB11, SMAL11, etc.).

## Project Structure

*   `index.js`: Main entry point.
*   `services/`:
    *   `economy.js`: Fetches Dollar and Selic.
    *   `stocks.js`: Logic for Stock screening.
    *   `fiis.js`: Logic for FII screening.
    *   `etfs.js`: ETF data.
