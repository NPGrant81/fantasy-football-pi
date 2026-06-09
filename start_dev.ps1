Write-Host "Starting Fantasy Football Pi Dev Environment..." -ForegroundColor Green

Write-Host "Starting Backend API (FastAPI) in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { .\backend\venv\Scripts\uvicorn.exe backend.main:app --reload }"

Write-Host "Starting Frontend UI (Vite) in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { cd frontend; npm run dev }"

Write-Host "Both servers are starting! Opening your browser in 3 seconds..." -ForegroundColor Green
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
