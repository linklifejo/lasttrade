import sqlite3

def check_all():
    conn = sqlite3.connect('trading.db')
    conn.row_factory = sqlite3.Row
    
    print("--- Detailed Holdings Assessment ---")
    rows = conn.execute('''
        SELECT h.code, h.qty, h.avg_price, p.current, (h.qty * p.current) as eval
        FROM mock_holdings h
        LEFT JOIN mock_prices p ON h.code = p.code
        WHERE h.qty > 0
    ''').fetchall()
    
    sum_eval = 0
    sum_pur = 0
    for row in rows:
        code = row['code']
        qty = row['qty']
        avg = row['avg_price']
        cur = row['current']
        eval_amt = row['eval'] if row['eval'] else 0
        pur_amt = qty * avg
        
        sum_eval += eval_amt
        sum_pur += pur_amt
        print(f"Code: {code}, Qty: {qty}, Avg: {avg:.2f}, Cur: {cur if cur else 'N/A'}, Eval: {eval_amt:,.0f}")
        
    print("-" * 40)
    print(f"Calculated Total Eval: {sum_eval:,.0f}")
    print(f"Calculated Total Pur: {sum_pur:,.0f}")
    
    acc = conn.execute("SELECT * FROM mock_account WHERE id=1").fetchone()
    if acc:
        print(f"DB mock_account - Cash: {acc['cash']:,.0f}, Total Eval: {acc['total_eval']:,.0f}")
        print(f"DB Total Asset (Calculated): {acc['cash'] + sum_eval:,.0f}")
    
    conn.close()

if __name__ == "__main__":
    check_all()
