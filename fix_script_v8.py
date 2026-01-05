# script_v8.js 수정: select 요소 비활성화/활성화 추가

with open('c:/lasttrade/static/script_v8.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# loadSettings 함수 시작 부분 찾기
for i, line in enumerate(lines):
    if 'async function loadSettings()' in line:
        # 다음 줄에 비활성화 코드 삽입
        lines.insert(i+2, '    const allSelects = document.querySelectorAll("select");\n')
        lines.insert(i+3, '    allSelects.forEach(sel => sel.disabled = true);\n')
        lines.insert(i+4, '    \n')
        break

# addLog 부분 찾아서 활성화 코드 삽입
for i, line in enumerate(lines):
    if '설정 로드 완료 (Mode:' in line:
        lines.insert(i, '        allSelects.forEach(sel => sel.disabled = false);\n')
        break

with open('c:/lasttrade/static/script_v8.js', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('✅ script_v8.js 수정 완료')
