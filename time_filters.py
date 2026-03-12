from datetime import datetime, time
import pandas as pd

class TimeFilters:
    def __init__(self):
        # Sessions in UTC (Adjust based on daylight savings if needed)
        self.killzones = {
            'Asia': (time(0, 0), time(6, 0)),
            'London': (time(7, 0), time(10, 0)),
            'NY': (time(12, 0), time(15, 0))
        }

    def is_killzone(self, current_time):
        """
        Checks if the current time falls within a defined Killzone.
        """
        for zone, (start, end) in self.killzones.items():
            if start <= current_time.time() <= end:
                return zone
        return None

    def get_true_open(self, df, current_time):
        """
        Tracks Midnight Open (00:00 UTC).
        """
        # Find the row corresponding to 00:00 UTC of the current day
        midnight_open = df[df.index.date == current_time.date()]
        if not midnight_open.empty:
            return midnight_open.iloc[0]['Open']
        return None

    def get_price_bias_relative_to_open(self, current_price, true_open):
        """
        Determines Premium vs Discount zone.
        Buy if price < True Open (Discount).
        Sell if price > True Open (Premium).
        """
        if true_open is None:
            return "Unknown"
        
        if current_price < true_open:
            return "Discount (Buy Zone)"
        elif current_price > true_open:
            return "Premium (Sell Zone)"
        else:
            return "Equilibrium"

    def is_valid_trading_window(self, current_time):
        """
        AMD Cycle: Only trade in London/NY Manipulation/Distribution.
        Avoid Asia consolidation.
        """
        zone = self.is_killzone(current_time)
        return zone in ['London', 'NY']

if __name__ == "__main__":
    # Test logic
    tf = TimeFilters()
    now = datetime.now()
    print(f"Current Zone: {tf.is_killzone(now)}")
    print(f"Valid to Trade: {tf.is_valid_trading_window(now)}")
    
    # Mock DF for testing open
    dates = pd.date_range("2023-01-01", periods=10, freq="H")
    mock_df = pd.DataFrame({'Open': range(10)}, index=dates)
    print(f"True Open Found: {tf.get_true_open(mock_df, dates[5])}")
