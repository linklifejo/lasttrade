from kiwoom_adapter import get_account_data
import json

def dump_real_summary():
    holdings, summary = get_account_data()
    print("--- RAW REAL SUMMARY ---")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    dump_real_summary()
