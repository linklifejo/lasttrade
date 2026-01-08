import os

log_file = os.path.join('logs', 'trading_20260108.log')
if not os.path.exists(log_file):
    print(f"Error: {log_file} not found")
else:
    with open(log_file, 'rb') as f:
        # Read last 5KB
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 5120))
        data = f.read()
        print(data.decode('utf-8', 'ignore'))
