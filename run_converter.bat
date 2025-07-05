@echo off
rem 이 명령어가 배치 파일이 있는 폴더로 강제로 이동시킵니다.
cd /d %~dp0

echo 대사 변환기 실행 중...
echo.
echo 브라우저가 자동으로 열립니다.
echo 종료하려면 이 창에서 Ctrl+C를 누르세요.
echo.
streamlit run dialogue_converter.py
pause