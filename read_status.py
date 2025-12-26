import os

file_path = r'c:\Users\sec7\Desktop\chapter_4\chapter_4\status.json'
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        print(f.read())
except Exception as e:
    print(f"Error reading status.json: {e}")
