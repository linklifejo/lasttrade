
import sqlite3

def update_db():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        key = 'early_stop_step'
        value = '4'
        
        # Check if exists
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        
        if row:
            cursor.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
            print(f"Update: {key} -> {value}")
        else:
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            print(f"Insert: {key} -> {value}")
            
        conn.commit()
        conn.close()
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()
