from bot import MainApp
import asyncio

async def check_rt_prices():
    # This might be tricky because we need the running instance.
    # But we can check the status.json which should have current prices.
    import json
    try:
        with open('status.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            stocks = data.get('holdings', [])
            for s in stocks:
                print(f"Name: {s.get('stk_nm')}, Profit: {s.get('pl_rt')}%")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_rt_prices())
