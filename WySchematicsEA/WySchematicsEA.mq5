//+------------------------------------------------------------------+
//|  WySchematicsEA.mq5                                              |
//|  Wyckoff Schematics — Phase-Based Scalping Expert Advisor        |
//|  Version : 1.0.0                                                 |
//|  Author  : kellwyn                                               |
//|                                                                  |
//|  STRATEGY OVERVIEW                                               |
//|  ─────────────────────────────────────────────────────────────── |
//|  Implements Richard Wyckoff's four-phase market cycle:           |
//|    Phase A – Accumulation  (Stop selling, PS/SC/AR/ST)           |
//|    Phase B – Markup        (Institutional markup, SOS/LPS)       |
//|    Phase C – Distribution  (Stop buying, PSY/BC/AR/UT/SOW/LPSY)  |
//|    Phase D – Markdown      (Institutional markdown)              |
//|                                                                  |
//|  Detection uses:                                                 |
//|    • Volume climax / dry-up analysis                             |
//|    • Price spread / bar-close analysis                           |
//|    • Trading range (TR) boundary mapping                         |
//|    • Spring / Upthrust (sweep) confirmation                      |
//|    • Sign of Strength (SOS) / Sign of Weakness (SOW) bars       |
//|                                                                  |
//|  CHANGELOG                                                       |
//|  ─────────────────────────────────────────────────────────────── |
//|  v1.0.0  2026-04-20  Initial release — phase scaffold,          |
//|                      all four phases + sub-phases,               |
//|                      scalp execution, risk management            |
//+------------------------------------------------------------------+
#property copyright "kellwyn"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

CTrade         Trade;
CPositionInfo  PosInfo;
CSymbolInfo    SymInfo;

//──────────────────────────────────────────────────────────────────
//  ENUMS
//──────────────────────────────────────────────────────────────────
enum ENUM_WY_PHASE
{
   WY_NONE         = 0,
   WY_ACCUMULATION = 1,
   WY_MARKUP       = 2,
   WY_DISTRIBUTION = 3,
   WY_MARKDOWN     = 4
};

enum ENUM_WY_SUBPHASE
{
   SUB_NONE = 0,
   // Accumulation sub-phases
   SUB_PS   = 1,   // Preliminary Support
   SUB_SC   = 2,   // Selling Climax
   SUB_AR   = 3,   // Automatic Rally
   SUB_ST   = 4,   // Secondary Test
   SUB_SPR  = 5,   // Spring / Sweep
   SUB_SOS  = 6,   // Sign of Strength
   SUB_LPS  = 7,   // Last Point of Support
   // Distribution sub-phases
   SUB_PSY  = 10,  // Preliminary Supply
   SUB_BC   = 11,  // Buying Climax
   SUB_AR_D = 12,  // Automatic Reaction (Distribution)
   SUB_UT   = 13,  // Upthrust / UTAD
   SUB_SOW  = 14,  // Sign of Weakness
   SUB_LPSY = 15   // Last Point of Supply
};

//──────────────────────────────────────────────────────────────────
//  INPUT PARAMETERS — PHASE TOGGLES
//──────────────────────────────────────────────────────────────────
input group "=== PHASE TRADING TOGGLES ==="
input bool  InpTradeAccumulation  = true;   // Trade Accumulation phase
input bool  InpTradeMarkup        = true;   // Trade Markup phase
input bool  InpTradeDistribution  = false;  // Trade Distribution phase
input bool  InpTradeMarkdown      = false;  // Trade Markdown phase

input group "=== SUB-PHASE TOGGLES (Accumulation) ==="
input bool  InpTrade_SC   = true;   // Enter on Selling Climax (SC)
input bool  InpTrade_ST   = true;   // Enter on Secondary Test (ST)
input bool  InpTrade_SPR  = true;   // Enter on Spring / Sweep
input bool  InpTrade_SOS  = true;   // Enter on Sign of Strength (SOS)
input bool  InpTrade_LPS  = true;   // Enter on Last Point of Support (LPS)

input group "=== SUB-PHASE TOGGLES (Distribution) ==="
input bool  InpTrade_BC   = false;  // Enter on Buying Climax (BC)
input bool  InpTrade_UT   = false;  // Enter on Upthrust (UT/UTAD)
input bool  InpTrade_SOW  = false;  // Enter on Sign of Weakness (SOW)
input bool  InpTrade_LPSY = false;  // Enter on Last Point of Supply (LPSY)

input group "=== TIMEFRAME ==="
input ENUM_TIMEFRAMES  InpTimeframe    = PERIOD_H1;   // Analysis timeframe
input ENUM_TIMEFRAMES  InpHTFTimeframe = PERIOD_H4;   // Higher timeframe confirmation
input int              InpLookback     = 200;          // Candles to analyse

input group "=== RISK MANAGEMENT ==="
input double InpRiskPercent    = 1.0;    // Risk per trade (% of balance)
input bool   InpUseRR          = true;   // Use Risk:Reward ratio
input double InpRRRatio        = 2.0;    // Risk:Reward ratio (when enabled)
input double InpFixedSLPips    = 15.0;   // Fixed stop-loss (pips) if RR off
input double InpFixedTPPips    = 30.0;   // Fixed take-profit (pips) if RR off
input double InpMaxLotSize     = 0.50;   // Hard cap on lot size
input double InpMinLotSize     = 0.01;   // Minimum lot size

input group "=== SCALPING FILTERS ==="
input int    InpMagicNumber    = 202604; // EA magic number
input int    InpMaxSpreadPips  = 3;      // Max spread allowed (pips)
input int    InpMaxOpenTrades  = 2;      // Max concurrent trades
input bool   InpConfirmHTF     = true;   // Require higher-TF trend confirmation
input int    InpVolLookback    = 20;     // Volume average lookback
input double InpVolSpikeMult   = 2.0;   // Volume spike multiplier for climax
input double InpVolDryupRatio  = 0.5;   // Volume dry-up ratio (relative to avg)
input int    InpATRPeriod      = 14;     // ATR period for SL/TP sizing
input bool   InpUseATRSizing   = true;  // Use ATR for SL sizing

//──────────────────────────────────────────────────────────────────
//  GLOBAL STATE
//──────────────────────────────────────────────────────────────────
ENUM_WY_PHASE    g_Phase    = WY_NONE;
ENUM_WY_SUBPHASE g_SubPhase = SUB_NONE;
double           g_TR_High  = 0.0;   // Trading Range high
double           g_TR_Low   = 0.0;   // Trading Range low
datetime         g_LastBar  = 0;

int g_ATRHandle  = INVALID_HANDLE;
int g_VolHandle  = INVALID_HANDLE;

//──────────────────────────────────────────────────────────────────
//  INIT / DEINIT
//──────────────────────────────────────────────────────────────────
int OnInit()
{
   Trade.SetExpertMagicNumber(InpMagicNumber);
   Trade.SetDeviationInPoints(20);

   g_ATRHandle = iATR(_Symbol, InpTimeframe, InpATRPeriod);
   if(g_ATRHandle == INVALID_HANDLE)
   {
      Print("WySchematicsEA: failed to create ATR indicator");
      return INIT_FAILED;
   }

   Print(StringFormat(
      "WySchematicsEA v1.0.0 | Symbol=%s | TF=%s | HTF=%s",
      _Symbol,
      EnumToString(InpTimeframe),
      EnumToString(InpHTFTimeframe)
   ));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_ATRHandle != INVALID_HANDLE) IndicatorRelease(g_ATRHandle);
}

//──────────────────────────────────────────────────────────────────
//  TICK
//──────────────────────────────────────────────────────────────────
void OnTick()
{
   // Only evaluate on new bar close
   datetime currentBar = iTime(_Symbol, InpTimeframe, 0);
   if(currentBar == g_LastBar) return;
   g_LastBar = currentBar;

   // Spread filter
   double spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   double maxSpread = InpMaxSpreadPips * _Point * 10;
   if(spread > maxSpread) return;

   // Load OHLCV data
   int bars = InpLookback;
   double high[], low[], close[], open[];
   long   volume[];
   ArraySetAsSeries(high,   true);
   ArraySetAsSeries(low,    true);
   ArraySetAsSeries(close,  true);
   ArraySetAsSeries(open,   true);
   ArraySetAsSeries(volume, true);

   if(CopyHigh(_Symbol,  InpTimeframe, 1, bars, high)   <= 0) return;
   if(CopyLow(_Symbol,   InpTimeframe, 1, bars, low)    <= 0) return;
   if(CopyClose(_Symbol, InpTimeframe, 1, bars, close)  <= 0) return;
   if(CopyOpen(_Symbol,  InpTimeframe, 1, bars, open)   <= 0) return;
   if(CopyTickVolume(_Symbol, InpTimeframe, 1, bars, volume) <= 0)
   {
      // fallback — real volume may not be available on all symbols
      ArrayResize(volume, bars);
      ArrayInitialize(volume, 1);
   }

   // Detect phase and subphase
   DetectPhase(high, low, close, open, volume, bars);

   // Check if we should trade current phase
   if(!PhaseIsEnabled()) return;

   // Higher timeframe confirmation
   if(InpConfirmHTF && !HTFTrendConfirms()) return;

   // Max open trades filter
   if(CountOpenTrades() >= InpMaxOpenTrades) return;

   // Generate signal
   int signal = GetSubPhaseSignal(high, low, close, open, volume, bars);
   if(signal == 0) return;

   ExecuteTrade(signal, close[0]);
}

//──────────────────────────────────────────────────────────────────
//  PHASE DETECTION
//──────────────────────────────────────────────────────────────────
void DetectPhase(const double &high[], const double &low[],
                 const double &close[], const double &open[],
                 const long &vol[], int bars)
{
   // Build trading range from recent swing high/low
   int trBars = MathMin(bars, 100);
   double rangeHigh = high[ArrayMaximum(high, 0, trBars)];
   double rangeLow  = low[ArrayMinimum(low,  0, trBars)];

   // Detect volume average
   double avgVol = 0;
   for(int i = 0; i < InpVolLookback && i < bars; i++) avgVol += (double)vol[i];
   avgVol /= InpVolLookback;

   double recentClose  = close[0];
   double rangeSize    = rangeHigh - rangeLow;
   double rangeMid     = rangeLow + rangeSize * 0.5;
   double upperQuarter = rangeLow + rangeSize * 0.75;
   double lowerQuarter = rangeLow + rangeSize * 0.25;

   bool climaxVolume = (vol[0] > avgVol * InpVolSpikeMult);
   bool dryupVolume  = (vol[0] < avgVol * InpVolDryupRatio);

   // Slope of close prices over last 20 bars (trend direction)
   double trendSlope = (close[0] - close[MathMin(19, bars-1)]) / MathMax(1, 19);

   // Broad phase classification using position in range + trend
   if(trendSlope < 0 && recentClose <= lowerQuarter)
   {
      // Price depressed — could be Accumulation or Markdown
      if(climaxVolume)
      {
         g_Phase    = WY_ACCUMULATION;
         g_SubPhase = SUB_SC;
      }
      else if(dryupVolume && g_Phase == WY_ACCUMULATION)
      {
         g_SubPhase = SUB_ST;  // Secondary test after SC
      }
      else if(recentClose < rangeLow)
      {
         g_SubPhase = SUB_SPR; // Spring / Sweep below range
      }
      else
      {
         g_Phase = WY_MARKDOWN;
         g_SubPhase = SUB_NONE;
      }
   }
   else if(trendSlope > 0 && recentClose >= upperQuarter)
   {
      // Price elevated — Markup or Distribution
      if(climaxVolume)
      {
         g_Phase    = WY_DISTRIBUTION;
         g_SubPhase = SUB_BC;
      }
      else if(recentClose > rangeHigh)
      {
         g_SubPhase = SUB_UT;  // Upthrust / UTAD above range
      }
      else if(trendSlope > 0 && g_Phase == WY_ACCUMULATION)
      {
         g_Phase    = WY_MARKUP;
         g_SubPhase = SUB_SOS; // Breakout from TR = SOS
      }
   }
   else if(g_Phase == WY_ACCUMULATION)
   {
      // Mid-range in Accumulation → look for LPS or SOS
      if(recentClose > rangeMid && vol[0] > avgVol * 1.2)
         g_SubPhase = SUB_SOS;
      else if(recentClose < rangeMid && dryupVolume)
         g_SubPhase = SUB_LPS;
      else if(recentClose <= lowerQuarter)
         g_SubPhase = SUB_ST;
   }
   else if(g_Phase == WY_DISTRIBUTION)
   {
      if(recentClose < rangeMid && vol[0] > avgVol * 1.3)
         g_SubPhase = SUB_SOW;
      else if(recentClose < rangeLow)
      {
         g_Phase    = WY_MARKDOWN;
         g_SubPhase = SUB_LPSY;
      }
   }

   // Update TR boundaries
   g_TR_High = rangeHigh;
   g_TR_Low  = rangeLow;
}

//──────────────────────────────────────────────────────────────────
//  PHASE ENABLED CHECK
//──────────────────────────────────────────────────────────────────
bool PhaseIsEnabled()
{
   switch(g_Phase)
   {
      case WY_ACCUMULATION: return InpTradeAccumulation;
      case WY_MARKUP:       return InpTradeMarkup;
      case WY_DISTRIBUTION: return InpTradeDistribution;
      case WY_MARKDOWN:     return InpTradeMarkdown;
      default:              return false;
   }
}

//──────────────────────────────────────────────────────────────────
//  SUB-PHASE SIGNAL
//  Returns:  1 = BUY, -1 = SELL, 0 = NO SIGNAL
//──────────────────────────────────────────────────────────────────
int GetSubPhaseSignal(const double &high[], const double &low[],
                      const double &close[], const double &open[],
                      const long &vol[], int bars)
{
   // Candle properties
   double body    = MathAbs(close[0] - open[0]);
   double range   = high[0] - low[0];
   double upperWick = high[0] - MathMax(close[0], open[0]);
   double lowerWick = MathMin(close[0], open[0]) - low[0];
   bool   bullBar = close[0] > open[0];
   bool   bearBar = close[0] < open[0];

   double avgVol = 0;
   for(int i = 0; i < InpVolLookback && i < bars; i++) avgVol += (double)vol[i];
   avgVol /= InpVolLookback;
   bool volAboveAvg = ((double)vol[0] > avgVol);

   switch(g_SubPhase)
   {
      case SUB_SC:
         if(!InpTrade_SC) return 0;
         // Selling climax: wide bear bar, closes off lows, big volume
         if(bearBar && vol[0] > avgVol * InpVolSpikeMult
            && lowerWick > body * 0.3) return 1; // Long reversal
         break;

      case SUB_ST:
         if(!InpTrade_ST) return 0;
         // Secondary test: lower volume, finds support near SC low
         if(bullBar && !volAboveAvg && close[0] > g_TR_Low) return 1;
         break;

      case SUB_SPR:
         if(!InpTrade_SPR) return 0;
         // Spring: sweeps below TR low, bullish reversal close
         if(low[0] < g_TR_Low && close[0] > g_TR_Low
            && bullBar && vol[0] > avgVol) return 1;
         break;

      case SUB_SOS:
         if(!InpTrade_SOS) return 0;
         // Sign of Strength: wide bull bar, strong close, vol expanding
         if(bullBar && vol[0] > avgVol * 1.5
            && close[0] > (high[0] - range * 0.25)) return 1;
         break;

      case SUB_LPS:
         if(!InpTrade_LPS) return 0;
         // LPS: test of SOS breakout point, low vol, bullish close
         if(bullBar && !volAboveAvg
            && close[0] > g_TR_Low + (g_TR_High - g_TR_Low) * 0.4) return 1;
         break;

      case SUB_BC:
         if(!InpTrade_BC) return 0;
         if(bullBar && vol[0] > avgVol * InpVolSpikeMult
            && upperWick > body * 0.3) return -1; // Short reversal
         break;

      case SUB_UT:
         if(!InpTrade_UT) return 0;
         if(high[0] > g_TR_High && close[0] < g_TR_High
            && bearBar) return -1;
         break;

      case SUB_SOW:
         if(!InpTrade_SOW) return 0;
         if(bearBar && vol[0] > avgVol * 1.5
            && close[0] < (low[0] + range * 0.25)) return -1;
         break;

      case SUB_LPSY:
         if(!InpTrade_LPSY) return 0;
         if(bearBar && !volAboveAvg
            && close[0] < g_TR_High - (g_TR_High - g_TR_Low) * 0.4) return -1;
         break;

      default:
         // Markup / Markdown — trend-follow on momentum
         if(g_Phase == WY_MARKUP && bullBar && volAboveAvg)  return 1;
         if(g_Phase == WY_MARKDOWN && bearBar && volAboveAvg) return -1;
         break;
   }
   return 0;
}

//──────────────────────────────────────────────────────────────────
//  HIGHER TIMEFRAME CONFIRMATION
//──────────────────────────────────────────────────────────────────
bool HTFTrendConfirms()
{
   double htfClose[];
   ArraySetAsSeries(htfClose, true);
   if(CopyClose(_Symbol, InpHTFTimeframe, 1, 50, htfClose) <= 0) return true;

   // Simple: 20-bar slope on HTF
   double slope = htfClose[0] - htfClose[19];

   if(g_Phase == WY_ACCUMULATION || g_Phase == WY_MARKUP)
      return slope >= 0; // HTF bullish or sideways
   if(g_Phase == WY_DISTRIBUTION || g_Phase == WY_MARKDOWN)
      return slope <= 0; // HTF bearish or sideways
   return true;
}

//──────────────────────────────────────────────────────────────────
//  TRADE EXECUTION
//──────────────────────────────────────────────────────────────────
void ExecuteTrade(int signal, double currentPrice)
{
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   double atrValue = 0.0;
   if(CopyBuffer(g_ATRHandle, 0, 1, 1, atrBuf) > 0)
      atrValue = atrBuf[0];

   double pipSize = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;
   double slDist  = InpUseATRSizing
                    ? atrValue * 1.5
                    : InpFixedSLPips * pipSize;
   double tpDist  = InpUseRR
                    ? slDist * InpRRRatio
                    : InpFixedTPPips * pipSize;

   double sl, tp;
   if(signal == 1) // BUY
   {
      sl = currentPrice - slDist;
      tp = currentPrice + tpDist;
   }
   else // SELL
   {
      sl = currentPrice + slDist;
      tp = currentPrice - tpDist;
   }

   double lots = CalcLotSize(slDist);

   string comment = StringFormat("WySch|%s|%s",
                                  PhaseLabel(g_Phase),
                                  SubPhaseLabel(g_SubPhase));

   if(signal == 1)
      Trade.Buy(lots, _Symbol, 0, sl, tp, comment);
   else
      Trade.Sell(lots, _Symbol, 0, sl, tp, comment);
}

//──────────────────────────────────────────────────────────────────
//  LOT SIZE CALCULATION
//──────────────────────────────────────────────────────────────────
double CalcLotSize(double slDist)
{
   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * InpRiskPercent / 100.0;

   double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize == 0 || tickValue == 0) return InpMinLotSize;

   double slTicks = slDist / tickSize;
   double lots    = riskAmount / (slTicks * tickValue);

   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(InpMinLotSize, MathMin(lots, InpMaxLotSize));
   return lots;
}

//──────────────────────────────────────────────────────────────────
//  UTILITIES
//──────────────────────────────────────────────────────────────────
int CountOpenTrades()
{
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PosInfo.SelectByIndex(i))
         if(PosInfo.Symbol() == _Symbol && PosInfo.Magic() == InpMagicNumber)
            count++;
   }
   return count;
}

string PhaseLabel(ENUM_WY_PHASE phase)
{
   switch(phase)
   {
      case WY_ACCUMULATION: return "Accumulation";
      case WY_MARKUP:       return "Markup";
      case WY_DISTRIBUTION: return "Distribution";
      case WY_MARKDOWN:     return "Markdown";
      default:              return "None";
   }
}

string SubPhaseLabel(ENUM_WY_SUBPHASE sub)
{
   switch(sub)
   {
      case SUB_PS:   return "PS";
      case SUB_SC:   return "SC";
      case SUB_AR:   return "AR";
      case SUB_ST:   return "ST";
      case SUB_SPR:  return "Spring";
      case SUB_SOS:  return "SOS";
      case SUB_LPS:  return "LPS";
      case SUB_PSY:  return "PSY";
      case SUB_BC:   return "BC";
      case SUB_AR_D: return "AR-D";
      case SUB_UT:   return "UT";
      case SUB_SOW:  return "SOW";
      case SUB_LPSY: return "LPSY";
      default:       return "—";
   }
}
//+------------------------------------------------------------------+
