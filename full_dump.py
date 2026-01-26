from kiwoom_adapter import get_account_data
import json

def full_dump():
    h, s = get_account_data()
    with open('full_summary_dump.json', 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    print("Dumped to full_summary_dump.json")

if __name__ == "__main__":
    full_dump()
