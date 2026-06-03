@echo off
:: =============================================================================
::  Legal Argument Mining — установка (Windows)
::  Использование: setup.bat [--skip-model]
:: =============================================================================
setlocal EnableDelayedExpansion

set "SKIP_MODEL=0"
for %%A in (%*) do (
    if /i "%%A"=="--skip-model" set "SKIP_MODEL=1"
)

:: read .env if exist
if exist ".env" (
    for /f "usebackq tokens=1,2 delims== eol=#" %%A in (".env") do (
        if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
    )
)

:: Default parameters
if not defined HF_MODEL_REPO set "HF_MODEL_REPO=google/gemma-3-4b-it-GGUF"
if not defined HF_MODEL_FILE set "HF_MODEL_FILE=gemma-3-4b-it-Q4_K_M.gguf"
if not defined HF_TOKEN set "HF_TOKEN="

echo ==============================================
echo   Legal Argument Mining Setup (Windows)
echo ==============================================

:: -- 1. Submodule --
echo.
echo [1/4] Initializing ArgumentMining submodule...
git submodule update --init --recursive
if errorlevel 1 ( echo ERROR: git submodule failed & exit /b 1 )
echo       OK

:: -- 2. Виртуальное окружение --
echo.
echo [2/4] Creating virtual environment (.venv)...
python -m venv .venv
if errorlevel 1 ( echo ERROR: python -m venv failed & exit /b 1 )
call .venv\Scripts\activate.bat
echo       OK

:: -- 3. Зависимости --
echo.
echo [3/4] Installing dependencies...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install huggingface_hub --quiet
if errorlevel 1 ( echo ERROR: pip install failed & exit /b 1 )
if exist "ArgumentMining-main\requirements.txt" (
    pip install -r ArgumentMining-main\requirements.txt --quiet
)
echo       OK

:: -- 4. Загрузка модели с Hugging Face --
echo.
if "%SKIP_MODEL%"=="1" (
    echo [4/4] Model download skipped --skip-model.
    echo       Use --provider heuristic or --provider gemini.
) else if exist "%HF_MODEL_FILE%" (
    echo [4/4] Model already exists: %HF_MODEL_FILE% - skipping.
) else (
    echo [4/4] Downloading model from Hugging Face...
    echo       Repository: %HF_MODEL_REPO%
    echo       File:       %HF_MODEL_FILE%
    if "%HF_TOKEN%"=="" (
        echo.
        echo WARNING: HF_TOKEN is not set.
        echo Some gated models require a token.
        echo Get one: https://huggingface.co/settings/tokens
        echo Copy .env.example to .env and set HF_TOKEN.
        echo.

    )
    python -c "from huggingface_hub import hf_hub_download; import os; path=hf_hub_download(repo_id=os.environ.get('HF_MODEL_REPO','%HF_MODEL_REPO%'), filename=os.environ.get('HF_MODEL_FILE','%HF_MODEL_FILE%'), local_dir='.', token=os.environ.get('HF_TOKEN') or None); print('Saved:', path)"
    if errorlevel 1 (
        echo ERROR during model download. Check HF_TOKEN and HF_MODEL_REPO in .env
        exit /b 1
    )
    echo       OK
)

echo.
echo ==============================================
echo   Installation completed successfully!
echo ==============================================
echo.
echo Run demo (no model or API keys required):
echo   python pipeline\\run_demo.py
echo.
echo Full pipeline with Gemini API (API key in .env):
echo   python pipeline\\run_full_pipeline.py --annotated data\\examples\\example_input.jsonl --output output\\ --provider gemini

endlocal
pause
