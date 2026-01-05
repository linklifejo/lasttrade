"""
index.html에서 인증 정보 섹션을 맨 위로 이동
"""

html_file = r'c:\lasttrade\templates\index.html'

with open(html_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 인증 정보 섹션 찾기 (574~653라인, 0-indexed로는 573~652)
auth_section_start = None
auth_section_end = None

for i, line in enumerate(lines):
    if '<!-- Category 4: Authentication & Security -->' in line:
        auth_section_start = i
    if auth_section_start is not None and '</div>\n' in line and 'settings-list' in lines[i-10:i][-1]:
        # settings-list의 닫는 태그 다음의 </div> 2개를 찾음
        if i > auth_section_start + 70:  # 충분히 뒤쪽
            auth_section_end = i + 2  # </div> 2개 포함
            break

if auth_section_start and auth_section_end:
    print(f"✅ 인증 섹션 발견: {auth_section_start+1}~{auth_section_end+1}라인")
    
    # 인증 섹션 추출
    auth_section = lines[auth_section_start:auth_section_end+1]
    
    # 원본에서 제거
    del lines[auth_section_start:auth_section_end+1]
    
    # settings-container 시작 위치 찾기
    insert_pos = None
    for i, line in enumerate(lines):
        if '<div class="settings-container">' in line:
            insert_pos = i + 1
            break
    
    if insert_pos:
        print(f"✅ 삽입 위치: {insert_pos+1}라인")
        
        # 인증 섹션을 맨 위에 삽입
        for j, auth_line in enumerate(auth_section):
            lines.insert(insert_pos + j, auth_line)
        
        # 저장
        with open(html_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print("✅ index.html 수정 완료! 인증 정보 섹션이 맨 위로 이동되었습니다.")
    else:
        print("❌ settings-container를 찾을 수 없습니다.")
else:
    print("❌ 인증 섹션을 찾을 수 없습니다.")
