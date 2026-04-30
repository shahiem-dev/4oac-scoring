@echo off
title 4OAC Scoring
cd /d "%~dp0"
set "PYTHONPATH=%APPDATA%\Python\Python314\site-packages;%PYTHONPATH%"
set "PYTHONNOUSERSITE="
echo Starting 4OAC Scoring app...
echo (Close this window to stop the app.)
echo.
"C:\Python314\python.exe" -m streamlit run Home.py
