import os

log_file = r'c:\Users\sec7\Desktop\chapter_4\chapter_4\logs\trading_20251226.log'

with open(log_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for line in lines[-50:]:
        print(line.strip())
