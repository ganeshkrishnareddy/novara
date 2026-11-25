$env:NOVARA_DB_PATH = 'D:\NOVARA\artifacts\final_qa_2026-11-24\qa_db\novara_qa.sqlite3'
$env:NOVARA_DEV_MODE = '1'
Set-Location 'D:\NOVARA\apps\api'
& 'D:\NOVARA\.venv\Scripts\python.exe' -m uvicorn novara_core.main:app --host 127.0.0.1 --port 8765 --log-level warning
