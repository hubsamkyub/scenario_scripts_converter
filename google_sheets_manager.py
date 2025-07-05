import pandas as pd
import re
import os
import streamlit as st
import json # 디버깅을 위해 추가

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
    구글 시트 API 관리 클래스 (v2.7 - 초정밀 디버깅 버전)
    """

    def __init__(self, service_account_file="service_account_key.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.service_account_file = os.path.join(base_dir, service_account_file)
        self.gc = None
        self._initialize_client()

    def _initialize_client(self):
        """
        [수정] 인증 과정의 모든 단계를 화면에 출력하여 원인을 추적합니다.
        """
        st.subheader("🕵️‍♂️ 구글 인증 디버그 로그")
        
        if not GSPREAD_AVAILABLE:
            st.error("❌ **[1단계] 라이브러리 확인 실패:** `gspread` 라이브러리를 찾을 수 없습니다. `requirements.txt` 파일을 확인하세요.")
            self.gc = None
            return False
        st.success("✅ **[1단계] 라이브러리 확인 성공:** `gspread` 라이브러리가 존재합니다.")

        try:
            is_deployed = os.environ.get('STREAMLIT_SERVER_PORT')

            if is_deployed:
                st.info("ℹ️ **[2단계] 환경 감지:** 웹 배포 환경(Streamlit Cloud)으로 인식했습니다.")
                
                # Secrets 전체가 존재하는지 확인
                if not hasattr(st, 'secrets') or not st.secrets:
                    st.error("❌ **[3단계] Secrets 확인 실패:** `st.secrets` 객체를 찾을 수 없거나 비어있습니다. Secrets 설정이 올바른지 확인하세요.")
                    return False
                
                # 특정 Secret 키가 있는지 확인
                if "gcp_service_account" in st.secrets:
                    st.success("✅ **[3단계] Secrets 확인 성공:** `[gcp_service_account]` 항목을 찾았습니다.")
                    creds_json = st.secrets["gcp_service_account"]
                    
                    # Secret 내용이 올바른 딕셔너리 형태인지 확인
                    if not isinstance(creds_json, dict):
                        st.error(f"❌ **[4단계] Secrets 내용 확인 실패:** `gcp_service_account`의 타입이 딕셔너리가 아닙니다 (현재 타입: {type(creds_json)}). `secrets.toml` 파일의 형식을 확인하세요.")
                        return False
                    
                    st.success(f"✅ **[4단계] Secrets 내용 확인 성공:** `gcp_service_account`는 올바른 딕셔너리 형태입니다. 포함된 키: `{list(creds_json.keys())}`")
                    
                    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    
                    # 자격 증명 생성 시도
                    try:
                        st.info("ℹ️ **[5단계] 자격 증명 생성 시도:** Secrets 정보로 구글 인증을 시도합니다.")
                        credentials = Credentials.from_service_account_info(creds_json, scopes=scope)
                        st.success("✅ **[5단계] 자격 증명 생성 성공!**")
                    except Exception as e:
                        st.error(f"❌ **[5단계] 자격 증명 생성 실패:** `Credentials.from_service_account_info`에서 오류가 발생했습니다. `private_key` 같은 Secrets 값이 올바른지 확인하세요. \n\n오류: `{e}`")
                        return False

                    # 최종 gspread 인증 시도
                    try:
                        st.info("ℹ️ **[6단계] 최종 인증 시도:** `gspread.authorize`를 호출합니다.")
                        self.gc = gspread.authorize(credentials)
                        st.success("🎉 **[6단계] 최종 인증 성공!** 구글 API에 연결되었습니다.")
                        return True
                    except Exception as e:
                        st.error(f"❌ **[6단계] 최종 인증 실패:** `gspread.authorize`에서 오류가 발생했습니다. 서비스 계정의 API 권한 또는 시트 공유 설정을 확인하세요. \n\n오류: `{e}`")
                        return False
                else:
                    st.error("❌ **[3단계] Secrets 확인 실패:** `secrets.toml` 파일 안에 `[gcp_service_account]` 섹션이 없습니다.")

            else:
                # 로컬 환경 로직 (이전과 동일)
                st.info("ℹ️ **[2단계] 환경 감지:** 로컬 개발 환경으로 인식했습니다.")
                if os.path.exists(self.service_account_file):
                    st.success(f"✅ **[3단계] 로컬 파일 확인 성공:** `{self.service_account_file}` 파일을 찾았습니다.")
                    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    credentials = Credentials.from_service_account_file(self.service_account_file, scopes=scope)
                    self.gc = gspread.authorize(credentials)
                    st.success("🎉 **최종 인증 성공!**")
                    return True
                else:
                    st.error(f"❌ **[3단계] 로컬 파일 확인 실패:** `{self.service_account_file}` 파일을 찾을 수 없습니다.")

            self.gc = None
            return False
            
        except Exception as e:
            st.error(f"🚨 **알 수 없는 오류 발생:** 클라이언트 초기화 중 예상치 못한 오류가 발생했습니다. \n\n오류: `{e}`")
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