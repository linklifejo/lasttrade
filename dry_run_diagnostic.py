import datetime
from market_hour import MarketHour
from get_setting import get_setting

def dry_run_check():
    now = datetime.datetime.now()
    current_time = now.strftime('%H:%M')
    is_trading_day = MarketHour.is_trading_day()
    
    auto_switch_enabled = get_setting('auto_mode_switch_enabled', True)
    real_switch_time = get_setting('real_mode_switch_time', '09:00')
    
    print(f"--- Dry Run Diagnostic ---")
    print(f"Current Local Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Is Trading Day: {is_trading_day}")
    print(f"Auto Switch Enabled: {auto_switch_enabled}")
    print(f"Real Mode Switch Time: {real_switch_time}")
    
    # Simulate 09:00 AM check
    sim_time = "09:00"
    current_mode = "Mock" # Assuming we are in Mock now
    
    can_switch = (real_switch_time <= sim_time < "12:00") and (current_mode == "Mock") and is_trading_day and auto_switch_enabled
    print(f"Will Switch trigger at 09:00? {'YES' if can_switch else 'NO'}")
    
    auto_start = get_setting('auto_start', False)
    print(f"Auto Start Setting: {auto_start}")

if __name__ == "__main__":
    dry_run_check()
