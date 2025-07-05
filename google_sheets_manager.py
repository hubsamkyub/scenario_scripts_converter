import pandas as pd
import re
import os
import streamlit as st
import json

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
    구글 시트 API 관리 클래스 (v2.9 - 최종)
    """

    def __init__(self, service_account_file="service_account_key.json"):
        # [함수명: __init__]: 변경 없음
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.service_account_file = os.path.join(base_dir, service_account_file)
        self.gc = None
        self._initialize_client()

    def _initialize_client(self):
        """
        [수정] 상세 디버깅 로그를 제거하고, 사이드바에 최종 상태만 표시합니다.
        """
        if not GSPREAD_AVAILABLE:
            st.sidebar.error("라이브러리 없음: `gspread`")
            return False

        try:
            # 1. 웹 배포 환경(Secrets) 우선 시도
            if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
                creds_json = st.secrets["gcp_service_account"]
                scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                credentials = Credentials.from_service_account_info(creds_json, scopes=scope)
                self.gc = gspread.authorize(credentials)
                st.sidebar.success("상태: 웹 배포 환경")
                return True
        except Exception:
            # Secrets 인증 실패 시 다음 단계로
            pass

        # 2. 로컬 파일 환경 시도
        try:
            if os.path.exists(self.service_account_file):
                scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                credentials = Credentials.from_service_account_file(self.service_account_file, scopes=scope)
                self.gc = gspread.authorize(credentials)
                st.sidebar.success("상태: 로컬 환경")
                return True
        except Exception:
            # 로컬 파일 인증도 실패 시 다음 단계로
            pass

        # 최종 실패
        self.gc = None
        st.sidebar.error("상태: 구글 API 연결 실패")
        return False

    def is_available(self):
        # [함수명: is_available]: 변경 없음
        return GSPREAD_AVAILABLE and self.gc is not None
    
    # 이하 다른 함수들은 변경 없음
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
            st.error(f"시트 목록 가져오기 실패: 이 단계에서 오류가 발생했다면, 서비스 계정이 시트에 '편집자'로 공유되었는지, 'Google Drive API'와 'Google Sheets API'가 활성화되었는지 확인하세요.")
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