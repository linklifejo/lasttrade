
from database_helpers import save_setting, get_setting
import sys

def main():
    print(f"Current target_stock_count: {get_setting('target_stock_count')}")
    res = save_setting('target_stock_count', 5.0)
    print(f"Manual Save result: {res}")
    print(f"New target_stock_count: {get_setting('target_stock_count')}")

if __name__ == "__main__":
    main()
