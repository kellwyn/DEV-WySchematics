"""
Trade executor — asks for manual confirmation before sending orders to MT5.
"""
from __future__ import annotations
import os
import MetaTrader5 as mt5
from .signals import Setup


def confirm_and_execute(setup: Setup, risk_percent: float, max_lot: float) -> None:
    print(f"\n  ┌ NEW SETUP DETECTED ─────────────────────────────")
    print(f"  │  {setup.symbol} | {setup.timeframe} | {setup.direction}")
    print(f"  │  Phase: {setup.phase}  Sub: {setup.subphase}")
    print(f"  │  Probability: {setup.probability:.1f}%")
    print(f"  │  Entry: {setup.entry:.5f}  |  ATR: {setup.atr:.5f}")
    print(f"  └──────────────────────────────────────────────────")

    try:
        answer = input("  Execute? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if answer != "y":
        print("  Skipped.\n")
        return

    _send_order(setup, risk_percent, max_lot)


def _send_order(setup: Setup, risk_percent: float, max_lot: float) -> None:
    balance  = mt5.account_info().balance
    risk_amt = balance * risk_percent / 100.0
    sl_dist  = setup.atr * 1.5
    tp_dist  = sl_dist * 2.0  # Default 1:2 RR

    tick_val  = mt5.symbol_info(setup.symbol).trade_tick_value
    tick_size = mt5.symbol_info(setup.symbol).trade_tick_size
    if tick_val == 0 or tick_size == 0:
        print("  Could not calculate lot size — aborted.")
        return

    sl_ticks = sl_dist / tick_size
    lots     = risk_amt / (sl_ticks * tick_val)
    lot_step = mt5.symbol_info(setup.symbol).volume_step
    lots     = max(0.01, min(round(lots / lot_step) * lot_step, max_lot))

    if setup.direction == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        sl = setup.entry - sl_dist
        tp = setup.entry + tp_dist
        price = mt5.symbol_info_tick(setup.symbol).ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        sl = setup.entry + sl_dist
        tp = setup.entry - tp_dist
        price = mt5.symbol_info_tick(setup.symbol).bid

    req = {
        "action":     mt5.TRADE_ACTION_DEAL,
        "symbol":     setup.symbol,
        "volume":     lots,
        "type":       order_type,
        "price":      price,
        "sl":         sl,
        "tp":         tp,
        "deviation":  20,
        "magic":      202604,
        "comment":    f"WyBot|{setup.phase}|{setup.subphase}",
        "type_time":  mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"  Order placed: {lots} lots | SL={sl:.5f} | TP={tp:.5f}\n")
    else:
        code = result.retcode if result else "N/A"
        print(f"  Order failed: retcode={code}\n")
