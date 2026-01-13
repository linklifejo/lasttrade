import subprocess
import threading
from logger import logger

def speak(text):
    """
    Windows PowerShell의 SpeechSynthesis를 사용하여 음성을 출력합니다.
    별도의 라이브러리 설치 없이 기본 기능을 사용하며, 메인 루프를 방해하지 않도록 스레드로 실행합니다.
    """
    def _speak():
        try:
            # PowerShell 명령어를 사용하여 TTS 실행
            # Korean 보이스가 설치되어 있어야 한국어로 나옵니다. (Windows 기본 사양)
            ps_command = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
            subprocess.run(["powershell", "-Command", ps_command], capture_output=True)
            logger.info(f"🔊 음성 보고: {text}")
        except Exception as e:
            logger.error(f"❌ 음성 출력 실패: {e}")

    threading.Thread(target=_speak, daemon=True).start()

if __name__ == "__main__":
    # 테스트 실행
    speak("음성 모듈이 활성화되었습니다. 라스트트레이드 시스템을 시작합니다.")
