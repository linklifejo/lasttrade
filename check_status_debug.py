import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database_helpers import get_system_status, get_current_status
    
    print("--- Calling get_system_status() ---")
    status = get_system_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))

    print("\n--- Calling get_current_status('MOCK') ---")
    # Force check mock status
    status_mock = get_current_status('MOCK')
    print(json.dumps(status_mock, indent=2, ensure_ascii=False))

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
