@echo off
title 4OAC Scoring
cd /d "%~dp0"
echo Starting 4OAC Scoring app...
echo (Close this window to stop the app.)
echo.
python -m streamlit run Home.py
