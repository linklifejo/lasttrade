import time
from database_helpers import save_setting, get_setting

def test_db_token():
    print("--- Testing DB Token Storage ---")
    
    # Simulate REAL token
    real_token = "TEST_REAL_TOKEN_999"
    save_setting('api_token_REAL', real_token)
    save_setting('api_token_time_REAL', str(time.time()))
    
    # Simulate MOCK token
    mock_token = "MOCK_TOKEN_12345"
    save_setting('api_token_MOCK', mock_token)
    save_setting('api_token_time_MOCK', str(time.time()))
    
    # Verify
    print(f"Stored REAL Token: {get_setting('api_token_REAL')}")
    print(f"Stored MOCK Token: {get_setting('api_token_MOCK')}")
    
    if get_setting('api_token_REAL') == real_token and get_setting('api_token_MOCK') == mock_token:
        print("✅ DB Token Storage Verification Successful")
    else:
        print("❌ DB Token Storage Verification Failed")

if __name__ == "__main__":
    test_db_token()
