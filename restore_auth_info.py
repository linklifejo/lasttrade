import sqlite3
import datetime
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def restore_defaults():
    print(f"Opening database: {DB_FILE}")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        data = {
            'real_app_key': 'ueEZm8xQX19MdIZDgr764cmS1ve5jogRVb9LpYVE-Rk',
            'real_app_secret': 'OHpBObbQNxebGpC7GKU5faXstXPzhdNestWebFMhb6A',
            'paper_app_key': 'I8zHt-F_c9LPHCab9S0IsaPAxW_2N4Wx0AXUKZ9fX0I',
            'paper_app_secret': 'lQcU0XYj0SzVxAf8P-f5Uv4wxxywGZbPZq-LMrt2_MQ',
            'telegram_chat_id': '8586247146',
            'telegram_token': '8597712986:AAEiRPcWHsVPkVNS3mp7CHDAahgpXAQm7rs',
            'my_account': '500081996340'
        }
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for k, v in data.items():
            print(f"Updating {k}...")
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at) 
                VALUES (?, ?, ?)
            ''', (k, v, timestamp))
            
        conn.commit()
        conn.close()
        print("✅ DB Restored Successfully")
    except Exception as e:
        print(f"❌ Error during restoration: {e}")

if __name__ == "__main__":
    restore_defaults()
