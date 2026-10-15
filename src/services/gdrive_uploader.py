import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service(creds_path='credentials.json', token_path='token.json'):
    """Авторизация и получение клиента Google Drive API."""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # Если токена нет или он устарел
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Первый запуск (выполняется на ПК для создания token.json)
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def upload_daily_csv(file_path: str, folder_id: str = None) -> bool:
    """Загрузка файла на Google Диск."""
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден.")
        return False

    service = get_drive_service()
    file_name = os.path.basename(file_path)

    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, mimetype='text/csv', resumable=True)

    print(f"Загрузка {file_name} в Google Диск...")
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f"Успешно загружено! ID файла: {uploaded_file.get('id')}")
    return True