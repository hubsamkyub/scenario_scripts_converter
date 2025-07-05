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
    구글 시트 API 관리 클래스 (v2.8 - 인증 로직 최종 수정)
    """

    def __init__(self, service_account_file="service_account_key.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.service_account_file = os.path.join(base_dir, service_account_file)
        self.gc = None
        self._initialize_client()

    def _initialize_client(self):
        """
        [수정] 환경을 예측하는 대신, Secrets 방식 우선 시도 후 실패 시 로컬 파일 방식으로 넘어갑니다.
        """
        st.subheader("🕵️‍♂️ 구글 인증 디버그 로그")
        
        if not GSPREAD_AVAILABLE:
            st.error("❌ **[오류] 라이브러리 확인 실패:** `gspread`가 설치되지 않았습니다.")
            return False
        st.success("✅ **[성공] 라이브러리 확인:** `gspread`가 존재합니다.")

        # --- 1. 웹 배포 환경(Secrets) 우선 시도 ---
        try:
            st.info("ℹ️ **[시도 1/2] Streamlit Secrets 인증을 시작합니다.")
            # st.secrets가 존재하고, 그 안에 키가 있는지 확인
            if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
                creds_json = st.secrets["gcp_service_account"]
                scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                credentials = Credentials.from_service_account_info(creds_json, scopes=scope)
                self.gc = gspread.authorize(credentials)
                st.success("🎉 **인증 성공!** Streamlit Secrets를 사용했습니다.")
                return True
            else:
                st.warning("⚠️ **[정보]** Secrets에 `[gcp_service_account]` 항목이 없습니다. 다음 단계를 시도합니다.")
        except Exception as e:
            st.warning(f"⚠️ **[정보]** Secrets 인증 중 오류가 발생하여 다음 단계를 시도합니다. (오류: {e})")

        # --- 2. 로컬 파일 환경 시도 ---
        try:
            st.info("ℹ️ **[시도 2/2] 로컬 `service_account_key.json` 파일 인증을 시작합니다.")
            if os.path.exists(self.service_account_file):
                scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                credentials = Credentials.from_service_account_file(self.service_account_file, scopes=scope)
                self.gc = gspread.authorize(credentials)
                st.success("🎉 **인증 성공!** 로컬 파일을 사용했습니다.")
                return True
            else:
                st.error(f"❌ **[실패]** 로컬 파일 '{os.path.basename(self.service_account_file)}'을 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"❌ **[실패]** 로컬 파일 인증 중 오류가 발생했습니다. (오류: {e})")

        # --- 최종 실패 ---
        self.gc = None
        st.error("🚨 **최종 인증 실패:** 모든 인증 방법을 시도했지만 구글 API에 연결할 수 없습니다.")
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