from datetime import datetime
import pandas as pd

class BasisLogic:
    def __init__(self, risk_free_rate_annual=0.10):
        self.risk_free_rate_annual = risk_free_rate_annual

    def parse_expiry(self, symbol):
        """
        Parses expiry date from symbol (e.g., BTCUSD_250627 -> June 27, 2025)
        """
        try:
            date_str = symbol.split('_')[1]
            # YYMMDD format
            expiry_date = datetime.strptime(date_str, "%y%m%d")
            # Usually expires at 08:00 UTC
            expiry_date = expiry_date.replace(hour=8, minute=0, second=0)
            return expiry_date
        except Exception as e:
            print(f"Error parsing expiry for {symbol}: {e}")
            return None

    def calculate_annualized_yield(self, spot_price, future_price, expiry_date):
        """
        Calculates the annualized yield (Basis) until expiry.
        Formula: ((Future / Spot) - 1) * (365 / Days_to_Expiry)
        """
        now = datetime.utcnow()
        days_to_expiry = (expiry_date - now).total_seconds() / (24 * 3600)
        
        if days_to_expiry <= 0 or spot_price <= 0:
            return 0
            
        premium = (future_price / spot_price) - 1
        annualized_yield = premium * (365 / days_to_expiry)
        return annualized_yield

    def get_best_contract(self, contracts_data):
        """
        Iterates over contracts and returns the one with the highest annualized yield.
        """
        best_yield = -1
        best_contract = None
        
        for c in contracts_data:
            if c['yield_apr'] > best_yield:
                best_yield = c['yield_apr']
                best_contract = c
                
        return best_contract

    def get_earliest_profitable_contract(self, contracts_data, threshold):
        """
        Returns the contract with the NEAREST expiry that is above the threshold.
        Useful for "diminuir o tempo" (reducing duration).
        """
        # Sort by expiry date (expiry_date is a string in results, should be compared as date)
        sorted_contracts = sorted(contracts_data, key=lambda x: x['expiry_date'])
        
        for c in sorted_contracts:
            if c['yield_apr'] >= threshold:
                return c
        return None
