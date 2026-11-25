$env:NOVARA_DB_PATH = 'D:\NOVARA\artifacts\final_qa_2026-11-24\qa_db\novara_migration_check.sqlite3'
$env:NOVARA_DEV_MODE = '1'
Set-Location 'D:\NOVARA\apps\api'
& 'D:\NOVARA\.venv\Scripts\python.exe' -m alembic upgrade head
"UPGRADE_EXIT=$LASTEXITCODE"
& 'D:\NOVARA\.venv\Scripts\python.exe' -m alembic check
"CHECK_EXIT=$LASTEXITCODE"
& 'D:\NOVARA\.venv\Scripts\python.exe' -m alembic heads
