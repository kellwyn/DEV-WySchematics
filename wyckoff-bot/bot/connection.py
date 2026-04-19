"""MT5 connection helpers."""
import MetaTrader5 as mt5


def connect():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
    info = mt5.account_info()
    if info is None:
        raise RuntimeError("Not logged in to MT5 account")
    print(f"  Connected: account #{info.login} | {info.server} | balance {info.balance:.2f}")


def disconnect():
    mt5.shutdown()
    print("  MT5 disconnected.")
