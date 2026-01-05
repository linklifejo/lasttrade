import re

html_file = r'c:\lasttrade\templates\index.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# selected 속성 제거 (공백 포함)
content = re.sub(r'\s+selected(?=>|\s)', '', content)

with open(html_file, 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ 모든 selected 속성 제거 완료')
