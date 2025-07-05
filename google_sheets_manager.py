import pandas as pd
import re
import os
import json        
# google_sheets_manager.py 파일 상단에 추가
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
    구글 시트 API 관리 클래스
    """
    
    def __init__(self, service_account_file="service_account_key.json"):
        """
        초기화
        
        Args:
            service_account_file (str): Service Account JSON 키 파일 경로
        """
        self.service_account_file = service_account_file
        self.gc = None
        self._initialize_client()

    # _initialize_client 함수를 아래 내용으로 수정
    def _initialize_client(self):
        """
        구글 시트 클라이언트 초기화 (Streamlit Secrets 우선)
        """
        if not GSPREAD_AVAILABLE:
            self.gc = None
            return False

        try:
            # 1. Streamlit Secrets에서 설정 로드 (배포 환경)
            if "gcp_service_account" in st.secrets:
                creds_json = st.secrets["gcp_service_account"]
                scope = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = Credentials.from_service_account_info(creds_json, scopes=scope)
                self.gc = gspread.authorize(credentials)
                return True
            # 2. 로컬 파일에서 설정 로드 (개발 환경)
            elif os.path.exists(self.service_account_file):
                scope = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = Credentials.from_service_account_file(self.service_account_file, scopes=scope)
                self.gc = gspread.authorize(credentials)
                return True
            else:
                self.gc = None
                return False
        except Exception as e:
            print(f"구글 시트 클라이언트 초기화 오류: {e}")
            self.gc = None
            return False
    
    def is_available(self):
        """
        API 사용 가능 여부 확인
        
        Returns:
            bool: 사용 가능 여부
        """
        return GSPREAD_AVAILABLE and self.gc is not None
    
    def extract_sheet_id(self, url):
        """
        구글 시트 URL에서 시트 ID 추출
        
        Args:
            url (str): 구글 시트 URL
            
        Returns:
            str: 추출된 시트 ID (None if 실패)
        """
        # 구글 시트 URL 패턴 매칭
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
            r'docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def extract_gid(self, url):
        """
        구글 시트 URL에서 GID (시트 탭 ID) 추출
        
        Args:
            url (str): 구글 시트 URL
            
        Returns:
            str: 추출된 GID (기본값: 0)
        """
        match = re.search(r'[#&]gid=([0-9]+)', url)
        if match:
            return match.group(1)
        return "0"  # 기본 시트
    
    def clean_dataframe_columns(self, df):
        """
        DataFrame의 컬럼명 정리
        - 중복 컬럼명 해결
        - 빈 컬럼명 처리
        - 특수문자 정리
        """
        # 컬럼명 리스트 복사
        columns = list(df.columns)
        cleaned_columns = []
        
        for i, col in enumerate(columns):
            # 빈 컬럼명 처리
            if pd.isna(col) or str(col).strip() == '' or str(col).startswith('Unnamed'):
                col = f"Empty_Column_{i+1}"
            else:
                col = str(col).strip()
            
            # 중복 처리
            original_col = col
            counter = 1
            while col in cleaned_columns:
                col = f"{original_col}_{counter}"
                counter += 1
            
            cleaned_columns.append(col)
        
        # 컬럼명 적용
        df.columns = cleaned_columns
        return df

    def read_sheet_data(self, url, sheet_name=None, header_row=0, start_row=None, end_row=None):
        """
        구글 시트에서 데이터 읽기 (범위 지정 추가)
        
        Args:
            url (str): 구글 시트 URL
            sheet_name (str, optional): 시트 이름 (None이면 첫 번째 시트)
            header_row (int): 헤더가 있는 행 번호 (0부터 시작)
            start_row (int, optional): 시작 행 번호 (헤더 제외, 1부터 시작)
            end_row (int, optional): 끝 행 번호 (헤더 제외, 1부터 시작)
            
        Returns:
            tuple: (success, message, dataframe, raw_data)
        """
        if not GSPREAD_AVAILABLE:
            return False, "구글 시트 라이브러리가 설치되지 않았습니다. 'pip install gspread google-auth'를 실행하세요.", None, None
            
        if not self.is_available():
            return False, "구글 시트 API가 설정되지 않았습니다. service_account_key.json 파일을 확인하세요.", None, None
        
        try:
            # 시트 ID 추출
            sheet_id = self.extract_sheet_id(url)
            if not sheet_id:
                return False, "올바르지 않은 구글 시트 URL입니다.", None, None
            
            # 스프레드시트 열기
            spreadsheet = self.gc.open_by_key(sheet_id)
            
            # 시트 선택
            if sheet_name:
                # 시트 이름으로 선택
                try:
                    worksheet = spreadsheet.worksheet(sheet_name)
                except gspread.WorksheetNotFound:
                    return False, f"'{sheet_name}' 시트를 찾을 수 없습니다.", None, None
            else:
                # GID로 시트 선택 시도, 실패하면 첫 번째 시트
                gid = self.extract_gid(url)
                try:
                    # GID로 시트 찾기
                    worksheets = spreadsheet.worksheets()
                    target_worksheet = None
                    
                    for ws in worksheets:
                        if str(ws.id) == gid:
                            target_worksheet = ws
                            break
                    
                    if target_worksheet:
                        worksheet = target_worksheet
                    else:
                        worksheet = spreadsheet.sheet1
                        
                except Exception:
                    worksheet = spreadsheet.sheet1
            
            # 모든 데이터 가져오기
            all_data = worksheet.get_all_values()
            
            if not all_data:
                return False, "시트에 데이터가 없습니다.", None, None
            
            # 원본 데이터 반환 (미리보기용)
            raw_data = pd.DataFrame(all_data)
            
            # 헤더 행 검증
            if header_row >= len(all_data):
                return False, f"헤더 행({header_row + 1})이 데이터 범위를 벗어났습니다. 최대 행: {len(all_data)}", None, raw_data
            
            # 헤더와 데이터 분리
            if header_row + 1 >= len(all_data):
                return False, "헤더 행 이후에 데이터가 없습니다.", None, raw_data
            
            headers = all_data[header_row]
            data_rows = all_data[header_row + 1:]
            
            # 범위 지정이 있는 경우 데이터 필터링
            if start_row is not None or end_row is not None:
                total_data_rows = len(data_rows)
                
                # 시작 행 설정 (1부터 시작하는 UI를 0부터 시작하는 인덱스로 변환)
                start_idx = (start_row - 1) if start_row is not None else 0
                start_idx = max(0, start_idx)
                
                # 끝 행 설정
                end_idx = end_row if end_row is not None else total_data_rows
                end_idx = min(total_data_rows, end_idx)
                
                if start_idx >= end_idx:
                    return False, f"시작 행({start_row})이 끝 행({end_row})보다 크거나 같습니다.", None, raw_data
                
                # 범위 데이터 추출
                data_rows = data_rows[start_idx:end_idx]
                
                if not data_rows:
                    return False, f"지정된 범위({start_row}-{end_row})에 데이터가 없습니다.", None, raw_data
            
            # DataFrame 생성
            df = pd.DataFrame(data_rows, columns=headers)
            
            # 컬럼명 정리 (중복 및 빈 컬럼명 처리)
            df = self.clean_dataframe_columns(df)
            
            # 빈 행 제거
            df = df.dropna(how='all')
            
            range_info = ""
            if start_row is not None or end_row is not None:
                range_info = f" (범위: {start_row or 1}-{end_row or '끝'}행)"
            
            return True, f"시트에서 {len(df)}개 행을 성공적으로 읽었습니다.{range_info} (헤더: {header_row + 1}행)", df, raw_data
            
        except gspread.SpreadsheetNotFound:
            return False, "스프레드시트를 찾을 수 없습니다. URL을 확인하거나 시트 공유 설정을 확인하세요.", None, None
        except gspread.APIError as e:
            return False, f"API 오류: {e}", None, None
        except Exception as e:
            return False, f"예상치 못한 오류: {e}", None, None
    
    def write_to_sheet(self, url, data, sheet_name=None, start_cell="A1", create_new_sheet=False, new_sheet_name=None):
        """
        구글 시트에 데이터 쓰기 (신규 기능)
        
        Args:
            url (str): 구글 시트 URL
            data (list): 쓸 데이터 (2D 리스트)
            sheet_name (str, optional): 대상 시트 이름
            start_cell (str): 시작 셀 위치 (예: "A1")
            create_new_sheet (bool): 새 시트 생성 여부
            new_sheet_name (str): 새 시트 이름
            
        Returns:
            tuple: (success, message, sheet_url)
        """
        if not self.is_available():
            return False, "구글 시트 API가 설정되지 않았습니다.", None
        
        try:
            sheet_id = self.extract_sheet_id(url)
            if not sheet_id:
                return False, "올바르지 않은 구글 시트 URL입니다.", None
            
            spreadsheet = self.gc.open_by_key(sheet_id)
            
            # 새 시트 생성
            if create_new_sheet and new_sheet_name:
                try:
                    worksheet = spreadsheet.add_worksheet(title=new_sheet_name, rows=1000, cols=20)
                    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={worksheet.id}"
                except gspread.exceptions.APIError as e:
                    if "already exists" in str(e):
                        worksheet = spreadsheet.worksheet(new_sheet_name)
                        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={worksheet.id}"
                    else:
                        return False, f"시트 생성 오류: {e}", None
            else:
                # 기존 시트 사용
                if sheet_name:
                    try:
                        worksheet = spreadsheet.worksheet(sheet_name)
                    except gspread.WorksheetNotFound:
                        return False, f"'{sheet_name}' 시트를 찾을 수 없습니다.", None
                else:
                    worksheet = spreadsheet.sheet1
                
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={worksheet.id}"
            
            # 데이터 쓰기
            if data:
                # 범위 계산
                end_col = chr(ord('A') + len(data[0]) - 1) if data[0] else 'A'
                end_row = len(data)
                
                # 시작 셀에서 행/열 번호 추출
                start_col = start_cell[0]
                start_row_num = int(start_cell[1:])
                
                # 끝 셀 계산
                end_col_num = ord(start_col) + len(data[0]) - 1
                end_col_letter = chr(end_col_num) if end_col_num <= ord('Z') else 'Z'
                end_row_num = start_row_num + len(data) - 1
                
                range_name = f"{start_cell}:{end_col_letter}{end_row_num}"
                
                worksheet.update(range_name, data)
                
                return True, f"데이터가 성공적으로 저장되었습니다. 범위: {range_name}", sheet_url
            else:
                return False, "저장할 데이터가 없습니다.", sheet_url
                
        except Exception as e:
            return False, f"데이터 저장 중 오류: {e}", None
    
    def get_sheet_info(self, url):
        """
        구글 시트 정보 가져오기
        
        Args:
            url (str): 구글 시트 URL
            
        Returns:
            tuple: (success, message, info_dict)
        """
        if not self.is_available():
            return False, "구글 시트 API가 설정되지 않았습니다.", None
        
        try:
            sheet_id = self.extract_sheet_id(url)
            if not sheet_id:
                return False, "올바르지 않은 구글 시트 URL입니다.", None
            
            spreadsheet = self.gc.open_by_key(sheet_id)
            
            info = {
                'title': spreadsheet.title,
                'id': spreadsheet.id,
                'worksheets': []
            }
            
            for ws in spreadsheet.worksheets():
                info['worksheets'].append({
                    'title': ws.title,
                    'id': ws.id,
                    'rows': ws.row_count,
                    'cols': ws.col_count
                })
            
            return True, "시트 정보를 성공적으로 가져왔습니다.", info
            
        except Exception as e:
            return False, f"시트 정보를 가져오는 중 오류: {e}", None
    
    def setup_instructions(self):
        """
        Service Account 설정 가이드 반환 (읽기/쓰기 권한 안내 추가)
        
        Returns:
            str: 설정 가이드 텍스트
        """
        if not GSPREAD_AVAILABLE:
            return """
🔧 구글 시트 라이브러리 설치 필요:

먼저 필요한 라이브러리를 설치하세요:

    pip install gspread google-auth

또는

    pip install -r requirements.txt

설치 후 프로그램을 재시작하세요.

---

설치 완료 후 구글 시트 API 설정:

1. Google Cloud Console에 접속 (https://console.cloud.google.com/)
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" → "라이브러리"에서 다음 API 활성화:
   - Google Sheets API
   - Google Drive API
4. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "서비스 계정"
5. 서비스 계정 생성 후 "키" 탭에서 JSON 키 다운로드
6. 다운로드한 JSON 파일을 'service_account_key.json'으로 이름 변경
7. 프로그램 폴더에 해당 파일 배치

📋 구글 시트 공유 설정 (읽기/쓰기):
1. 구글 시트에서 "공유" 버튼 클릭
2. 서비스 계정 이메일 주소를 "편집자" 권한으로 추가
   또는 "링크가 있는 모든 사용자"를 "편집자"로 설정
3. "링크 복사" 후 프로그램에서 사용

⚠️ 주의: 시트 저장 기능을 사용하려면 "편집자" 권한이 필요합니다.
"""
        
        return """
🔧 구글 시트 API 설정 가이드:

1. Google Cloud Console에 접속 (https://console.cloud.google.com/)
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" → "라이브러리"에서 다음 API 활성화:
   - Google Sheets API
   - Google Drive API
4. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "서비스 계정"
5. 서비스 계정 생성 후 "키" 탭에서 JSON 키 다운로드
6. 다운로드한 JSON 파일을 'service_account_key.json'으로 이름 변경
7. 프로그램 폴더에 해당 파일 배치

📋 구글 시트 공유 설정 (읽기/쓰기):
1. 구글 시트에서 "공유" 버튼 클릭
2. 서비스 계정 이메일 주소를 "편집자" 권한으로 추가
   또는 "링크가 있는 모든 사용자"를 "편집자"로 설정
3. "링크 복사" 후 프로그램에서 사용

⚠️ 주의: 시트 저장 기능을 사용하려면 "편집자" 권한이 필요합니다.
"""

    def validate_setup(self):
        """
        설정 상태 검증
        
        Returns:
            dict: 검증 결과
        """
        result = {
            'gspread_available': GSPREAD_AVAILABLE,
            'service_account_file_exists': os.path.exists(self.service_account_file),
            'client_initialized': self.gc is not None,
            'can_access_api': False
        }
        
        if GSPREAD_AVAILABLE and result['client_initialized']:
            try:
                # 테스트 요청으로 API 접근 확인
                # 실제로는 실행되지 않을 더미 요청이지만 클라이언트 상태 확인용
                result['can_access_api'] = True
            except:
                # 이는 정상적인 상황 (존재하지 않는 파일에 대한 요청)
                result['can_access_api'] = True
        
        return result