import os
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from rich.console import Console
from rich.theme import Theme

# Load env variables first
load_dotenv()

# Setup rich console for styled output
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "danger": "bold red"
})
console = Console(theme=custom_theme)

class RiskManager:
    """
    RiskManager: Intercepts ML decisions and enforces hard safety limits.
    Configurable via CLI arguments and .env.
    """
    def __init__(self):
        self._parse_config()
        self.cooldown_until = None

        # Ensure log directory exists
        os.makedirs("results", exist_ok=True)
        self.log_file = "results/risk_audit.log"

        # Cooldown period (in hours)
        self.cooldown_hours = 24

    def _parse_config(self):
        """Parse configuration combining CLI args and .env"""
        parser = argparse.ArgumentParser(description="BTC Bot with Risk Management")
        
        # Risk specific arguments
        parser.add_argument("--stop-loss", type=float, default=None,
                            help="Percentage to trigger an immediate sell (e.g., 0.02 for 2%%)")
        parser.add_argument("--take-profit", type=float, default=None,
                            help="Target percentage to lock in gains (e.g., 0.03 for 3%%)")
        parser.add_argument("--trailing-stop", type=float, default=None,
                            help="Dynamic stop-loss percentage that follows price action upwards")
        parser.add_argument("--max-drawdown", type=float, default=None,
                            help="Daily account-wide drawdown limit to stop the bot for 24h")
        parser.add_argument("--risk-mode", choices=['aggressive', 'conservative', 'manual-override'], default=None,
                            help="Risk mode")

        # Parse known args so we don't break if other parts of the app use argparse
        args, _ = parser.parse_known_args()
        
        # Set values: CLI > ENV > Default
        self.stop_loss = args.stop_loss if args.stop_loss is not None else float(os.getenv("RISK_STOP_LOSS", "0.015"))
        self.take_profit = args.take_profit if args.take_profit is not None else float(os.getenv("RISK_TAKE_PROFIT", "0.03"))
        self.trailing_stop = args.trailing_stop if args.trailing_stop is not None else float(os.getenv("RISK_TRAILING_STOP", "0.005"))
        self.max_drawdown = args.max_drawdown if args.max_drawdown is not None else float(os.getenv("RISK_MAX_DRAWDOWN", "0.05"))
        self.mode = args.risk_mode if args.risk_mode is not None else os.getenv("RISK_MODE", "conservative")
        self.atr_multiplier = float(os.getenv("RISK_ATR_MULTIPLIER", "2.0"))
        
        # Kelly Criterion Settings
        self.kelly_fractional = 0.5 # 0.5x Kelly (Fractional) for safety
        self.max_kelly_cap = 0.20 # Max 20% of equity per trade (Permite R$ 200 em banca de R$ 1000)
        self.ego_multiplier = 1.0 # 1.0 = full trust, 0.3 = extreme doubt
        
        # Bunker State (Protecao Ativa)
        self.bunker_mode = False
        self.target_hedge_pct = 0.0 # 0.0 a 0.9 (90% Bunker)
        self.last_rebalance_ts = 0

        # Tracking peak prices for trailing stop: { "asset": { "pos_id": peak_price } }
        self.peak_prices = {}

        # Tracking daily peak equity for max drawdown
        self.daily_peak_equity = None
        self.last_equity_reset = datetime.now().date()

    def _log_audit(self, message):
        """Log risk events to audit file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def _trigger_cooldown(self, reason):
        """Trigger mandatory cooldown period"""
        self.cooldown_until = datetime.now() + timedelta(hours=self.cooldown_hours)
        msg = f"[RISK] Mandatory cooldown triggered for {self.cooldown_hours}h. Reason: {reason}"
        console.print(msg, style="danger")
        self._log_audit(msg)

    def is_in_cooldown(self):
        """Check if bot is in a cooldown period"""
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True
        elif self.cooldown_until and datetime.now() >= self.cooldown_until:
            # Cooldown expired
            self.cooldown_until = None
            msg = "[RISK] Cooldown period has ended. Resuming normal operations."
            console.print(msg, style="info")
            self._log_audit(msg)
            return False
        return False

    def update_equity_high(self, current_equity):
        """Update daily peak equity for max drawdown checks"""
        # Reset daily peak on a new day
        current_date = datetime.now().date()
        if current_date > self.last_equity_reset:
            self.daily_peak_equity = current_equity
            self.last_equity_reset = current_date
            return

        if self.daily_peak_equity is None or current_equity > self.daily_peak_equity:
            self.daily_peak_equity = current_equity

    def check_max_drawdown(self, current_equity):
        """Check if daily max drawdown limit is hit"""
        if self.daily_peak_equity is None:
            return False

        drawdown = (self.daily_peak_equity - current_equity) / self.daily_peak_equity
        if drawdown >= self.max_drawdown:
            reason = f"Max Drawdown Hit: {drawdown*100:.2f}% (Limit: {self.max_drawdown*100:.2f}%)"
            self._trigger_cooldown(reason)
            return True

        return False

    def check_exit_conditions(self, asset, pos_id, current_price, entry_price, signal_direction, ml_signal='HOLD', atr_value: Optional[float] = None):
        """
        Check hard risk limits against current position.
        Overrides ML signal if necessary.

        Args:
            asset: Symbol name (e.g., BTCBRL)
            pos_id: Unique identifier for the position (to track trailing stops)
            current_price: Current market price
            entry_price: Price the position was opened at
            signal_direction: 1 for long, -1 for short
            ml_signal: The signal proposed by the ML model ('BUY', 'SELL', 'HOLD')
            atr_value: Average True Range for volatility-based stops

        Returns:
            str: Action to take ('SELL' if risk triggered, otherwise ml_signal)
            str: Reason for the action
        """
        # Ensure asset is initialized in peak tracking
        if asset not in self.peak_prices:
            self.peak_prices[asset] = {}

        # Initialize peak price for this position if not exists
        if pos_id not in self.peak_prices[asset]:
            self.peak_prices[asset][pos_id] = current_price

        # Update peak price if moving in favorable direction
        if signal_direction == 1: # Long
            if current_price > self.peak_prices[asset][pos_id]:
                self.peak_prices[asset][pos_id] = current_price
        else: # Short
            if current_price < self.peak_prices[asset][pos_id]:
                self.peak_prices[asset][pos_id] = current_price

        peak_price = self.peak_prices[asset][pos_id]
        
        # Calculate current PnL percentage
        pnl_pct = ((current_price / entry_price) - 1) * signal_direction
        
        # 1. Check Stop Loss
        effective_stop_loss = self.stop_loss
        if atr_value and atr_value > 0:
            # Distancia do stop em porcentagem baseada no ATR
            atr_stop_pct = (atr_value * self.atr_multiplier) / entry_price
            # Usamos o maior dos dois para evitar stops curtos demais em baixa volatilidade
            # ou longos demais em alta volatilidade (opcional: poderiamos usar apenas o ATR)
            effective_stop_loss = max(self.stop_loss, atr_stop_pct)
            
        if pnl_pct <= -effective_stop_loss:
            msg = f"[RISK] Stop-Loss triggered at {pnl_pct*100:.2f}% (Effective SL: {effective_stop_loss*100:.2f}%). Overriding ML '{ml_signal}' signal."
            console.print(msg, style="danger")
            self._log_audit(msg)
            # Remove from tracking
            if asset in self.peak_prices and pos_id in self.peak_prices[asset]:
                del self.peak_prices[asset][pos_id]
            return "SELL", "HARD_STOP_LOSS"
            
        # 2. Check Trailing Stop
        # Calculate pullback from peak
        pullback_pct = ((current_price / peak_price) - 1) * signal_direction
        
        # Only activate trailing stop if we are in profit
        if pnl_pct > 0 and pullback_pct <= -self.trailing_stop:
            msg = f"[RISK] Trailing Stop triggered. Peak: {peak_price:.2f}, Current: {current_price:.2f}, Drop: {pullback_pct*100:.2f}%. Overriding ML '{ml_signal}' signal."
            console.print(msg, style="warning")
            self._log_audit(msg)
            # Remove from tracking
            del self.peak_prices[asset][pos_id]
            return "SELL", "TRAILING_STOP"

        # 3. Check Take Profit
        if pnl_pct >= self.take_profit:
            msg = f"[RISK] Take-Profit reached at {pnl_pct*100:.2f}%. Overriding ML '{ml_signal}' signal."
            console.print(msg, style="info")
            self._log_audit(msg)
            # Remove from tracking
            del self.peak_prices[asset][pos_id]
            return "SELL", "TAKE_PROFIT"

        return ml_signal, None

    def cleanup_tracking(self, asset, pos_id):
        """Remove tracking for closed positions"""
        if asset in self.peak_prices and pos_id in self.peak_prices[asset]:
            del self.peak_prices[asset][pos_id]

    def check_liquidation_risk(self, entry_price, current_price, leverage):
        """
        Check liquidation risk distance for margin/futures trades.
        Returns (distance_pct, liquidation_price).
        """
        if leverage <= 1.0:
            return 1.0, 999999999
            
        # Simplified long liquidation formula: Liquidation Price = Entry Price * (Leverage / (Leverage - 1))
        # Note: Short liquidation price would be: Entry Price * (Leverage / (Leverage + 1))
        liq_price = entry_price * (leverage / (leverage - 1))

        distance = (liq_price - current_price) / current_price
        return max(0.0, distance), liq_price

    def calculate_kelly_fraction(self, accuracy, risk_reward_ratio=None):
        """
        Calcula a fragao ideal de alocacao usando o Criterio de Kelly.
        Formula: f* = (p(b+1) - 1) / b
        Onde p = acuracia (probabilidade), b = ratio (take_profit / stop_loss)
        """
        p = accuracy
        b = risk_reward_ratio if risk_reward_ratio else (self.take_profit / self.stop_loss)
        
        if b <= 0 or p <= 0: return 0.0
        
        kelly_f = (p * (b + 1) - 1) / b
        
        # Aplicar Kelly Fracionario + Calibracao de Ego (Auto-Correcao)
        final_f = kelly_f * self.kelly_fractional * self.ego_multiplier
        
        # Trava de seguranca (Nao alocar mais que o max_kelly_cap da banca)
        return max(0.0, min(final_f, self.max_kelly_cap))

    def calibrate_ego_buffer(self, realized_acc, expected_acc=0.65):
        """
        Ajusta o ego_multiplier. Se expected > realized significativamente, reduz o risco.
        O bot percebe que esta 'se achando demais' ou o mercado mudou.
        """
        gap = expected_acc - realized_acc
        if gap > 0.10: # Se o bot acha que acerta 65% mas acerta < 55%
             self.ego_multiplier = max(0.3, self.ego_multiplier - 0.1)
             msg = f"[RISK] AUTO-CORRECAO: Reduzindo Ego Buffer para {self.ego_multiplier:.2f} (Gap: {gap:.1%})"
             console.print(msg, style="warning")
             self._log_audit(msg)
        elif gap < 0.02: # Se esta performando conforme o esperado ou melhor
             self.ego_multiplier = min(1.0, self.ego_multiplier + 0.05)
             if self.ego_multiplier < 1.0:
                msg = f"[RISK] AUTO-CORRECAO: Restaurando Ego Buffer para {self.ego_multiplier:.2f}"
                console.print(msg, style="info")
                self._log_audit(msg)

    def calculate_bunker_allocation(self, macro_risk: float) -> float:
        """
        Determina a porcentagem do capital total que deve estar em Hedge (USDT/XAUT).
        - Risk < 0.4: 0% Hedge (Alpha Full)
        - Risk 0.4-0.75: 60% Hedge (Protecao Dinamica)
        - Risk > 0.75: 90% Hedge (Estado Bunker - Mantem 10% de Honra em BTC)
        """
        if macro_risk > 0.75:
            self.target_hedge_pct = 0.90
            self.bunker_mode = True
        elif macro_risk > 0.40:
            self.target_hedge_pct = 0.60
            self.bunker_mode = True
        else:
            # Desalocacao Gradual (Return to Risk)
            if self.target_hedge_pct > 0:
                self.target_hedge_pct = max(0.0, self.target_hedge_pct - 0.20)
                print(f"[BUNKER] Desalocação Gradual Iniciada: Alvo de Hedge em {self.target_hedge_pct:.1%}")
            else:
                self.bunker_mode = False
        
        return self.target_hedge_pct

    def get_kelly_trade_amount(self, total_equity, accuracy):
        """Converte a fracao de Kelly em valor BRL nominal."""
        fraction = self.calculate_kelly_fraction(accuracy)
        recommended_amount = total_equity * fraction
        
        # Logica de seguranca: Se a acuracia for baixa (< 50%), Kelly sera zero.
        # Nesses casos, retornamos 0 para impedir a entrada de baixo valor estatistico.
        return recommended_amount
