@echo off
rem Start the React dev server on http://localhost:5173
cd /d "%~dp0frontend"
if not exist node_modules (
  echo Installing npm dependencies...
  call npm install
)
npm run dev
