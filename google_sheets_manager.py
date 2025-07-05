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
    구글 시트 API 관리 클래스 (v2.5)
    """

    def __init__(self, service_account_file="service_account_key.json"):
        # [함수명: __init__]: 변경 없음
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.service_account_file = os.path.join(base_dir, service_account_file)
        self.gc = None
        self._initialize_client()

    def _initialize_client(self):
        # [함수명: _initialize_client]: 변경 없음
        if not GSPREAD_AVAILABLE:
            self.gc = None
            return False
        try:
            is_deployed = os.environ.get('STREAMLIT_SERVER_PORT')
            if is_deployed:
                if st.secrets.get("gcp_service_account"):
                    creds_json = st.secrets["gcp_service_account"]
                    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    credentials = Credentials.from_service_account_info(creds_json, scopes=scope)
                    self.gc = gspread.authorize(credentials)
                    return True
            else:
                if os.path.exists(self.service_account_file):
                    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    credentials = Credentials.from_service_account_file(self.service_account_file, scopes=scope)
                    self.gc = gspread.authorize(credentials)
                    return True
            self.gc = None
            return False
        except Exception as e:
            print(f"구글 시트 클라이언트 초기화 중 예상치 못한 오류 발생: {e}")
            self.gc = None
            return False

    def is_available(self):
        # [함수명: is_available]: 변경 없음
        return GSPREAD_AVAILABLE and self.gc is not None

    def extract_sheet_id(self, url):
        # [함수명: extract_sheet_id]: 변경 없음
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
            r'docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_sheet_names(self, url):
        # [함수명: get_sheet_names]: 변경 없음
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
        except gspread.exceptions.SpreadsheetNotFound:
            return False, "스프레드시트를 찾을 수 없습니다. URL을 확인하거나 시트 공유 설정을 확인하세요.", None
        except Exception as e:
            return False, f"시트 목록을 가져오는 중 오류 발생: {e}", None

    def read_sheet_data(self, url, sheet_name):
        """
        [수정] 헤더를 소문자로 변환하고, 원본 행 번호를 추가하는 로직을 적용합니다.
        """
        if not self.is_available():
            return False, "구글 시트 API가 설정되지 않았습니다.", None
        try:
            sheet_id = self.extract_sheet_id(url)
            if not sheet_id:
                return False, "올바르지 않은 구글 시트 URL입니다.", None

            spreadsheet = self.gc.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            data = worksheet.get_all_values()
            
            header_row_index = 3  # 헤더는 4번째 행 (인덱스 3)
            data_start_row = 4    # 데이터는 5번째 행부터 시작

            if not data or len(data) < data_start_row + 1:
                return False, "시트에 데이터가 부족합니다. (최소 5줄 필요)", None
            
            header = data[header_row_index]
            actual_data = data[data_start_row:]
            
            df = pd.DataFrame(actual_data, columns=header)
            
            # [수정] 모든 컬럼명을 소문자로 통일 (양쪽 공백 제거 포함)
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            # [신규] '원본 행 번호' 컬럼 추가 (엑셀의 실제 행 번호)
            # 데이터 시작 행 번호(5)부터 DataFrame 길이에 맞게 번호 부여
            df.insert(0, '원본 행 번호', range(data_start_row + 1, data_start_row + 1 + len(df)))

            df.dropna(how='all', inplace=True)
            return True, f"'{sheet_name}' 시트에서 {len(df)}개 행을 성공적으로 읽었습니다. (헤더: 4행)", df
        except gspread.exceptions.WorksheetNotFound:
            return False, f"'{sheet_name}' 시트를 찾을 수 없습니다.", None
        except Exception as e:
            return False, f"데이터를 읽어오는 중 오류 발생: {e}", None