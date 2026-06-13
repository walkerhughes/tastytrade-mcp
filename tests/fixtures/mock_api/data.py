"""Deterministic fixture data for the mock Tastytrade API.

Values are internally consistent so verifiers can assert exact numbers:
  - Account 5WT00001, customer "me".
  - SPY trades around 200; the 2026-04-17 chain is centered on the 200 strike.
  - AAPL trades around 210.
"""

ACCOUNT = "5WT00001"
CUSTOMER_ID = "me"

ACCOUNTS = {
    "data": {
        "items": [
            {
                "account": {
                    "account-number": ACCOUNT,
                    "account-type-name": "Margin",
                    "nickname": "Main",
                    "margin-or-cash": "Margin",
                    "is-closed": False,
                }
            }
        ]
    }
}

TRADING_STATUS = {
    "data": {
        "account-number": ACCOUNT,
        "options-level": "Advanced",
        "day-trade-count": 0,
        "is-frozen": False,
        "is-closed-positions-only": False,
    }
}

BALANCES = {
    "data": {
        "account-number": ACCOUNT,
        "net-liquidating-value": "52000.00",
        "cash-balance": "20000.00",
        "equity-buying-power": "40000.00",
        "derivative-buying-power": "30000.00",
        "maintenance-requirement": "12000.00",
        "cash-available-to-withdraw": "20000.00",
        "pending-cash": "0.00",
    }
}

# Two positions with known P/L:
#   AAPL: 100 @ 150 open, mark 155 -> +500
#   SPY 200C x2 @ 4.00 open, mark 5.00, mult 100 -> +200
# total unrealized P/L = +700
POSITIONS = {
    "data": {
        "items": [
            {
                "symbol": "AAPL",
                "instrument-type": "Equity",
                "underlying-symbol": "AAPL",
                "quantity": "100",
                "quantity-direction": "Long",
                "average-open-price": "150.00",
                "mark-price": "155.00",
                "close-price": "154.00",
                "multiplier": "1",
            },
            {
                "symbol": "SPY   260417C00200000",
                "instrument-type": "Equity Option",
                "underlying-symbol": "SPY",
                "quantity": "2",
                "quantity-direction": "Long",
                "average-open-price": "4.00",
                "mark-price": "5.00",
                "close-price": "4.80",
                "multiplier": "100",
            },
        ]
    }
}

NET_LIQ_HISTORY = {
    "data": {
        "items": [
            {"time": "2026-05-01", "close": "50000.00"},
            {"time": "2026-05-08", "close": "53000.00"},
            {"time": "2026-05-15", "close": "47000.00"},  # trough -> drawdown from 53000
            {"time": "2026-05-22", "close": "51000.00"},
            {"time": "2026-06-01", "close": "52000.00"},
        ]
    }
}

TRANSACTIONS = {
    "data": {
        "items": [
            {
                "id": 1001,
                "transaction-type": "Trade",
                "transaction-sub-type": "Buy to Open",
                "symbol": "AAPL",
                "underlying-symbol": "AAPL",
                "quantity": "100",
                "price": "150.00",
                "net-value": "15000.00",
                "net-value-effect": "Debit",
                "commission": "0.00",
                "clearing-fees": "0.10",
                "regulatory-fees": "0.05",
                "executed-at": "2026-05-02T14:30:00Z",
                "description": "Bought 100 AAPL @ 150.00",
            },
            {
                "id": 1002,
                "transaction-type": "Trade",
                "transaction-sub-type": "Sell to Close",
                "symbol": "AAPL",
                "underlying-symbol": "AAPL",
                "quantity": "100",
                "price": "155.00",
                "net-value": "15500.00",
                "net-value-effect": "Credit",
                "commission": "0.00",
                "clearing-fees": "0.10",
                "regulatory-fees": "0.07",
                "executed-at": "2026-05-20T15:00:00Z",
                "description": "Sold 100 AAPL @ 155.00",
            },
            {
                "id": 1003,
                "transaction-type": "Money Movement",
                "transaction-sub-type": "Dividend",
                "symbol": "AAPL",
                "underlying-symbol": "AAPL",
                "net-value": "24.00",
                "net-value-effect": "Credit",
                "executed-at": "2026-05-15T00:00:00Z",
                "description": "AAPL dividend",
            },
        ],
        "pagination": {"total-pages": 1, "page-offset": 0},
    }
}

LIVE_ORDERS = {
    "data": {
        "items": [
            {
                "id": 555,
                "status": "Live",
                "order-type": "Limit",
                "time-in-force": "Day",
                "underlying-symbol": "SPY",
                "price": "1.50",
                "price-effect": "Debit",
                "received-at": "2026-06-12T13:00:00Z",
                "legs": [
                    {
                        "symbol": "SPY   260417C00205000",
                        "action": "Buy to Open",
                        "quantity": "1",
                        "remaining-quantity": "1",
                        "instrument-type": "Equity Option",
                    }
                ],
            }
        ]
    }
}

ORDER_HISTORY = {
    "data": {
        "items": [
            {
                "id": 400,
                "status": "Filled",
                "order-type": "Market",
                "time-in-force": "Day",
                "underlying-symbol": "AAPL",
                "received-at": "2026-05-02T14:29:00Z",
                "legs": [{"symbol": "AAPL", "action": "Buy", "quantity": "100", "instrument-type": "Equity"}],
            }
        ]
    }
}

SYMBOL_SEARCH = {
    "AAPL": {"data": {"items": [{"symbol": "AAPL", "description": "Apple Inc.", "instrument-type": "Equity"}]}},
    "SPY": {"data": {"items": [{"symbol": "SPY", "description": "SPDR S&P 500 ETF", "instrument-type": "Equity"}]}},
}

EQUITIES = {
    "AAPL": {"data": {"symbol": "AAPL", "description": "Apple Inc.", "listed-market": "NASDAQ", "active": True}},
    "SPY": {"data": {"symbol": "SPY", "description": "SPDR S&P 500 ETF", "listed-market": "ARCA", "active": True}},
}

MARKET_METRICS = {
    "AAPL": {
        "symbol": "AAPL",
        "implied-volatility-index": "0.2800",
        "implied-volatility-index-rank": "42.50",
        "implied-volatility-percentile": "55.00",
        "liquidity-rating": "4",
        "beta": "1.25",
    },
    "SPY": {
        "symbol": "SPY",
        "implied-volatility-index": "0.1500",
        "implied-volatility-index-rank": "30.00",
        "implied-volatility-percentile": "40.00",
        "liquidity-rating": "5",
        "beta": "1.00",
    },
}

DIVIDENDS = {
    "AAPL": {"data": {"items": [{"amount": "0.24", "occurred-date": "2026-05-15"}]}},
}

EARNINGS = {
    "AAPL": {"data": {"items": [{"occurred-date": "2026-05-01", "eps": "1.52"}]}},
}

# Equity + option quotes keyed by symbol. Option mids around the 200 strike are closest
# (call 5.00 / put 5.00) so ATM detection lands on 200.
QUOTES = {
    "AAPL": {
        "symbol": "AAPL",
        "bid": 210.40,
        "ask": 210.60,
        "last": 210.50,
        "mid": 210.50,
        "close": 208.00,
        "volume": 500000,
    },
    "SPY": {
        "symbol": "SPY",
        "bid": 199.95,
        "ask": 200.05,
        "last": 200.00,
        "mid": 200.00,
        "close": 198.00,
        "volume": 1000000,
    },
    "SPY   260417C00195000": {
        "symbol": "SPY   260417C00195000",
        "bid": 8.0,
        "ask": 8.4,
        "mid": 8.2,
        "volume": 100,
        "open-interest": 400,
        "implied-volatility": 0.18,
    },
    "SPY   260417P00195000": {
        "symbol": "SPY   260417P00195000",
        "bid": 2.9,
        "ask": 3.1,
        "mid": 3.0,
        "volume": 120,
        "open-interest": 500,
        "implied-volatility": 0.20,
    },
    "SPY   260417C00200000": {
        "symbol": "SPY   260417C00200000",
        "bid": 4.9,
        "ask": 5.1,
        "mid": 5.0,
        "volume": 900,
        "open-interest": 2500,
        "implied-volatility": 0.16,
    },
    "SPY   260417P00200000": {
        "symbol": "SPY   260417P00200000",
        "bid": 4.9,
        "ask": 5.1,
        "mid": 5.0,
        "volume": 850,
        "open-interest": 2300,
        "implied-volatility": 0.17,
    },
    "SPY   260417C00205000": {
        "symbol": "SPY   260417C00205000",
        "bid": 2.9,
        "ask": 3.1,
        "mid": 3.0,
        "volume": 300,
        "open-interest": 700,
        "implied-volatility": 0.15,
    },
    "SPY   260417P00205000": {
        "symbol": "SPY   260417P00205000",
        "bid": 7.9,
        "ask": 8.1,
        "mid": 8.0,
        "volume": 80,
        "open-interest": 350,
        "implied-volatility": 0.19,
    },
}


def _strike(price: str, c: str, p: str) -> dict:
    return {"strike-price": price, "call": c, "put": p}


OPTION_CHAIN = {
    "data": {
        "items": [
            {
                "underlying-symbol": "SPY",
                "expirations": [
                    {
                        "expiration-date": "2026-04-17",
                        "days-to-expiration": 17,
                        "expiration-type": "Regular",
                        "settlement-type": "PM",
                        "strikes": [
                            _strike("195.0", "SPY   260417C00195000", "SPY   260417P00195000"),
                            _strike("200.0", "SPY   260417C00200000", "SPY   260417P00200000"),
                            _strike("205.0", "SPY   260417C00205000", "SPY   260417P00205000"),
                        ],
                    },
                    {
                        "expiration-date": "2026-06-19",
                        "days-to-expiration": 80,
                        "expiration-type": "Regular",
                        "settlement-type": "PM",
                        "strikes": [
                            _strike("200.0", "SPY   260619C00200000", "SPY   260619P00200000"),
                        ],
                    },
                ],
            }
        ]
    }
}

WATCHLISTS = {"data": {"items": [{"name": "My Tech"}]}}
PUBLIC_WATCHLISTS = {"data": {"items": [{"name": "Tom's Watchlist"}]}}
WATCHLIST_DETAIL = {
    "My Tech": {"data": {"name": "My Tech", "watchlist-entries": [{"symbol": "AAPL"}, {"symbol": "MSFT"}]}},
}
PUBLIC_WATCHLIST_DETAIL = {
    "Tom's Watchlist": {
        "data": {"name": "Tom's Watchlist", "watchlist-entries": [{"symbol": "SPY"}, {"symbol": "QQQ"}]}
    },
}
