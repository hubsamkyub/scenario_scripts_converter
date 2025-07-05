# google_sheets_manager.py

import pandas as pd
import re
import os
import streamlit as st

# 구글 시트 라이브러리 선택적 가져오기
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None
    Credentials = None

class GoogleSheetsManager:
    """
    구글 시트 API 관리 클래스 (v2.6 - 디버깅 강화 버전)
    """

    def __init__(self, service_account_file="service_account_key.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.service_account_file = os.path.join(base_dir, service_account_file)
        self.gc = None
        self._initialize_client()

    def _initialize_client(self):
        if not GSPREAD_AVAILABLE:
            st.error("디버그: gspread 라이브러리가 설치되지 않았습니다.")
            self.gc = None
            return False

        try:
            is_deployed = os.environ.get('STREAMLIT_SERVER_PORT')

            if is_deployed:
                st.info("디버그: 웹 배포 환경으로 인식했습니다.")
                if st.secrets.get("gcp_service_account"):
                    st.success("디버그: Streamlit Secrets에서 [gcp_service_account]를 찾았습니다.")
                    creds_json = st.secrets["gcp_service_account"]
                    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    
                    st.info("디버그: 구글 서버에 인증을 시도합니다...")
                    credentials = Credentials.from_service_account_info(creds_json, scopes=scope)
                    self.gc = gspread.authorize(credentials)
                    st.success("디버그: 구글 API 인증에 성공했습니다!")
                    return True
                else:
                    st.error("디버그: 웹 배포 환경이지만 Streamlit Secrets에 [gcp_service_account]가 설정되지 않았습니다.")

            else:
                st.info("디버그: 로컬 환경으로 인식했습니다.")
                if os.path.exists(self.service_account_file):
                    st.success(f"디버그: 로컬에서 {self.service_account_file} 파일을 찾았습니다.")
                    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    
                    st.info("디버그: 구글 서버에 인증을 시도합니다...")
                    credentials = Credentials.from_service_account_file(self.service_account_file, scopes=scope)
                    self.gc = gspread.authorize(credentials)
                    st.success("디버그: 구글 API 인증에 성공했습니다!")
                    return True
                else:
                    st.error(f"디버그: 로컬 환경이지만 {self.service_account_file} 파일을 찾을 수 없습니다.")

            self.gc = None
            return False
            
        except Exception as e:
            st.error(f"디버그: 구글 시트 클라이언트 초기화 중 예상치 못한 오류 발생: {e}")
            self.gc = None
            return False

    def is_available(self):
        return GSPREAD_AVAILABLE and self.gc is not None

    def extract_sheet_id(self, url):
        patterns = [r'/spreadsheets/d/([a-zA-Z0-9-_]+)', r'docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_sheet_names(self, url):
        if not self.is_available():
            return False, "구글 시트 API가 설정되지 않았습니다.", None
        try:
            sheet_id = self.extract_sheet_id(url)
            if not sheet_id:
                return False, "올바르지 않은 구글 시트 URL입니다.", None
            spreadsheet = self.gc.open_by_key(sheet_id)
            worksheets = spreadsheet.worksheets()
            sheet_names = [ws.title for ws in worksheets]
            return True, "시트 목록을 성공적으로 불러왔습니다.", sheet_names
        except Exception as e:
            return False, f"시트 목록을 가져오는 중 오류 발생: {e}", None

    def read_sheet_data(self, url, sheet_name):
        if not self.is_available():
            return False, "구글 시트 API가 설정되지 않았습니다.", None
        try:
            sheet_id = self.extract_sheet_id(url)
            if not sheet_id:
                return False, "올바르지 않은 구글 시트 URL입니다.", None

            spreadsheet = self.gc.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            data = worksheet.get_all_values()
            
            header_row_index = 3
            data_start_row = 4

            if not data or len(data) < data_start_row + 1:
                return False, "시트에 데이터가 부족합니다. (최소 5줄 필요)", None
            
            header = data[header_row_index]
            actual_data = data[data_start_row:]
            df = pd.DataFrame(actual_data, columns=header)
            
            df.columns = [str(col).strip().lower() for col in df.columns]
            df.insert(0, '원본 행 번호', range(data_start_row + 1, data_start_row + 1 + len(df)))

            df.dropna(how='all', inplace=True)
            return True, f"'{sheet_name}' 시트에서 {len(df)}개 행을 성공적으로 읽었습니다. (헤더: 4행)", df
        except Exception as e:
            return False, f"데이터를 읽어오는 중 오류 발생: {e}", None