#!/usr/bin/env python
"""
This script generates a summary of the Stock-Trak performance.

The standard deviation is computed with daily returns and the Sharpe Ratio uses the geometric average daily returns.
The date range used in the above calculations is May 28, 2018 until the current data.

Input files required in current working directory:
    settings.csv - Contains the following settings.
        risk_free_name (str):  The risk free asset name.
        benchmark_name (str):  The benchmark asset name.
        market_name (str):  The market index name.
    stocks/[risk_free_name].csv - Yahoo formatted historical performance of risk free asset.
    [benchmark_name].csv - Yahoo Finance formatted historical performance of benchmark asset.
    [market_name].csv - Yahoo Finance formatted historical performance of market index.
    OpenPosition.csv - Contains the current Stock-Trak portfolio.
    portfolio_history.csv - Contains the historical performance of the Stock-Trak account.
"""

from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from os.path import join
import pandas as pd
from scipy.stats.mstats import gmean
from sklearn import linear_model
from sklearn.metrics import r2_score

# ***************************************************************************************
# Set version number
# ***************************************************************************************
__version__ = '1.0'


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Main body of Code
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

start_date = datetime(2018, 5, 28)

# Read the settings
# -----------------------------------------------------------------------------------
settings = pd.read_csv("settings.csv", index_col="name", squeeze=True)
settings = settings.str.strip()

# Read Risk-Free performance
# -----------------------------------------------------------------------------------
name = join("stocks", settings["risk_free_name"] + ".csv")
risk_free = pd.read_csv(name, parse_dates=["Date"], usecols=["Date", "Adj Close"])
risk_free.set_index("Date", inplace=True)
risk_free = risk_free.resample('D').interpolate()
start_price = risk_free.loc[start_date, "Adj Close"]
risk_free['Return'] = 100.0 * (risk_free['Adj Close'] - start_price) / start_price
risk_free['Daily_Return'] = risk_free['Adj Close'].pct_change()
risk_free = risk_free.loc[risk_free.index > start_date, :]
r_f = 100.0 * (gmean(risk_free['Daily_Return'] + 1.0) - 1.0)
risk_free['Daily_Return'] = risk_free['Daily_Return'] * 100.0
std_f = risk_free['Daily_Return'].std()

# Read benchmark, market and portfolio data
# -----------------------------------------------------------------------------------
total_r = pd.DataFrame(0.0, index=risk_free.index, columns=["market", "benchmark", "portfolio"])
daily_r = pd.DataFrame(0.0, index=risk_free.index, columns=["market", "benchmark", "portfolio"])
stats = pd.DataFrame()
for name in total_r.columns:
    if name == "portfolio":
        data = pd.read_csv("portfolio_history.csv", parse_dates=["Date"], usecols=["Date", "Value"])
    else:
        data = pd.read_csv(settings["{}_name".format(name)] + ".csv", parse_dates=["Date"],
                           usecols=["Date", "Adj Close"])
        data.rename(index=str, columns={"Adj Close": "Value"}, inplace=True)

    data.set_index("Date", inplace=True)
    data = data.resample('D').interpolate()
    data = data.loc[data.index >= start_date]
    start_price = data.loc[start_date, "Value"]
    total_r[name] = 100.0 * (data['Value'] - start_price) / start_price - risk_free['Return']
    daily_r[name] = data['Value'].pct_change()
    stats.loc["mean_r", name] = 100.0 * (gmean(daily_r[name].loc[daily_r[name].index > start_date] + 1.0) - 1.0)
    daily_r[name] = 100.0 * daily_r[name]
    stats.loc["std", name] = daily_r[name].std()
    stats.loc["Sharpe", name] = (stats.loc["mean_r", name] - r_f) / (stats.loc["std", name] - std_f)

# Determine CAPM beta and Security Characteristic Line (SCL)
# -----------------------------------------------------------------------------------
r_m = daily_r["market"] - risk_free['Daily_Return']
for name in total_r.columns:
    r = daily_r[name] - risk_free['Daily_Return']
    model = linear_model.LinearRegression()
    model.fit(r_m.values.reshape(-1, 1), r.values.reshape(-1, 1))
    r_predict = model.predict(r_m.values.reshape(-1, 1))
    stats.loc["beta", name] = model.coef_[0, 0]
    stats.loc["alpha", name] = model.intercept_[0]
    stats.loc["Treynor", name] = (stats.loc["mean_r", name] - r_f) / stats.loc["beta", name]
    stats.loc["info", name] = stats.loc["alpha", name] / stats.loc["std", name]
    p_star = stats.loc["std", "market"] / stats.loc["std", name] * (stats.loc["mean_r", name] - r_f) + r_f
    stats.loc["M2", name] = p_star - stats.loc["mean_r", "market"]

    fig, ax = plt.subplots()
    ax.scatter(r_m, r)
    ax.plot(r_m, r_predict)
    ax.set_title("SCL for the {}, beta = {:.2f}, alpha = {:.2f}%, R^2 = {:.2f}".format(name, model.coef_[0, 0],
                                                                                       model.intercept_[0],
                                                                                       r2_score(r, r_predict)))
    plt.ylabel("Excess Daily Return (%)")
    plt.xlabel("Excess Daily Market Return (%)")
    ax.axhline(y=0.0, c='black')
    ax.axvline(x=0.0, c='black')
    ax.set_ylim(-2, 2)
    plt.grid(True)
    fig.savefig('scl_{}.png'.format(name))
    plt.close()

print(stats)
stats.to_csv("stats.csv")

# Plot the returns
# -----------------------------------------------------------------------------------
fig, ax = plt.subplots()
label = "Benchmark (Daily Geo. Mean r={:.2f}%, std={:.2f}%, sharpe={:.2f})".format(stats.loc["mean_r", "benchmark"],
                                                                                   stats.loc["std", "benchmark"],
                                                                                   stats.loc["Sharpe", "benchmark"])
ax.plot(total_r.benchmark, label=label, marker=".")
label = "Portfolio (Daily Geo. Mean r={:.2f}%, std={:.2f}%, sharpe={:.2f})".format(stats.loc["mean_r", "portfolio"],
                                                                                   stats.loc["std", "portfolio"],
                                                                                   stats.loc["Sharpe", "portfolio"])
ax.plot(total_r.portfolio, label=label, marker=".")
ax.set_title("Benchmark ({}) and Portfolio Performance".format(settings["benchmark_name"]))
plt.ylabel("% Cumulative Returns above Risk-Free ({})".format(settings["risk_free_name"]))

x = total_r.index.tolist()[-1]
for y in [total_r.portfolio.iloc[-1], total_r.benchmark.iloc[-1]]:
    plt.annotate("{:.1f}%".format(y), xy=(x, y), xytext=(-40, 10), textcoords='offset points', ha='right', va='bottom',
                 bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.8),
                 arrowprops=dict(arrowstyle='fancy', connectionstyle='arc3,rad=0'))

ax.set_ylim(top=8.0)
lgd = ax.legend(loc='upper left', fancybox=True, shadow=True, ncol=1, fontsize=9)
plt.grid(True)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%d"))
fig.autofmt_xdate()
fig.savefig('summary.png', bbox_extra_artists=(lgd,), bbox_inches='tight')
plt.close()


# Read current portfolio
# -----------------------------------------------------------------------------------
current_portfolio = pd.read_csv("OpenPosition.csv", usecols=["Currency", "MarketValue"])
currency = current_portfolio.groupby("Currency").sum()
currency["Percent"] = 100.0 * currency["MarketValue"] / currency["MarketValue"].sum()

# Plot currency distribution
# -----------------------------------------------------------------------------------
ax = currency.plot.pie(y="MarketValue", title="Currency Exposures", figsize=(5, 5))
ax.legend(labels=["{}, {:.1f}%".format(n, currency.loc[n, "Percent"]) for n in currency.index])
ax.set_ylabel("")
fig = ax.get_figure()
fig.savefig('currency.png')
plt.close()
