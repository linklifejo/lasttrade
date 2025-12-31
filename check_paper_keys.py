from database_helpers import get_setting

paper_key = get_setting('paper_app_key')
paper_secret = get_setting('paper_app_secret')

print(f"Paper App Key: {paper_key}")
print(f"Paper App Secret: {paper_secret}")
print(f"Key length: {len(paper_key) if paper_key else 0}")
print(f"Secret length: {len(paper_secret) if paper_secret else 0}")
