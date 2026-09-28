@echo off

REM Vai para a raiz do projeto
cd /d "%~dp0.."

REM Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo ERRO: ambiente virtual .venv nao encontrado.
    echo Execute primeiro: python -m venv .venv
    echo Depois instale: python -m pip install -r requirements.txt
    exit /b 1
)

REM Executa a automacao usando o Python do projeto
".venv\Scripts\python.exe" "src\parte2_relatorio_semanal.py"

REM Retorna o codigo da execucao
exit /b %errorlevel%
