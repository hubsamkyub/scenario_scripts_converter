# 대사 변환기 프로그램 사용 안내

이 프로그램은 구글 시트에 있는 게임 대사 데이터를 변환하는 도구입니다.

## 사전 준비 (최초 1회)

이 프로그램을 사용하려면 구글 시트 API 접근을 위한 인증 키 파일이 필요합니다.

1.  **Google Cloud Platform(GCP)에 접속하여 `service_account_key.json` 파일을 다운로드하세요.**
    -   [자세한 발급 방법 가이드 링크](https://developers.google.com/workspace/guides/create-credentials?hl=ko#create_credentials_for_a_service_account) 등을 참고할 수 있습니다.
    -   **"Google Sheets API"** 와 **"Google Drive API"** 가 활성화되어 있어야 합니다.
2.  다운로드한 **JSON 파일의 이름을 `service_account_key.json`으로 변경**하세요.
3.  변경한 파일을 이 프로그램 폴더 안에 넣어주세요.
4.  **구글 시트 공유 설정**: 데이터를 불러올 구글 시트의 **'공유'** 버튼을 누르고, `service_account_key.json` 파일 내용 안에 있는 `client_email` 주소를 **'편집자(Editor)'** 권한으로 추가해주세요.

## 프로그램 실행 방법

1.  폴더 안의 `명령 프롬프트 실행.bat` 파일을 더블클릭하거나, 터미널을 열어 아래 명령어를 입력하세요.
2.  `pip install -r requirements.txt` 를 실행하여 필요한 라이브러리를 설치합니다. (최초 1회)
3.  `streamlit run dialogue_converter.py` 를 실행하면 웹 브라우저에서 프로그램이 열립니다.

## 문의

문제가 발생하면 개발자에게 문의하세요.