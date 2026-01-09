
with open('c:/lasttrade/settings_ui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'add_field' in line:
            print("-" * 50)
            print(f"Line {i+1}: {line.strip()}")
            # 다음 1~3줄도 출력해서 콤보박스 값을 확인
            if i+1 < len(lines): print(f"  {lines[i+1].strip()}")
            if i+2 < len(lines): print(f"  {lines[i+2].strip()}")
            if i+3 < len(lines): print(f"  {lines[i+3].strip()}")
