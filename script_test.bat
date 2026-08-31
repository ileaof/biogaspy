@echo off
setlocal
REM ============================================================
REM  script_test.bat -- fluxo MEA da tese (BioGasSim)
REM  Cria o projeto, ajusta a composicao do feed e roda a
REM  varredura de composicao exportando para Excel.
REM ============================================================

echo(
echo [1/3] Criando projeto MEA (test_mea)...
biogassim new test_mea --tech mea
if errorlevel 1 goto :erro

echo(
echo [2/3] Definindo composicao do feed (CH4=0.63 CO2=0.36 H2S=0.01 )...
biogassim set CH4=0.63 CO2=0.36 H2S=0.01 --case test_mea/case.json
if errorlevel 1 goto :erro

echo(
echo [3/3] Varredura de composicao CH4=0.40:0.70:0.05 -^> test.xlsx ...
biogassim sweep CH4=0.40:0.70:0.05 --out test_mea/test.csv
if errorlevel 1 goto :erro

echo(
echo Concluido. Saidas: test_mea\case.json e test.xlsx
goto :fim

:erro
echo(
echo *** ERRO na etapa anterior (errorlevel %errorlevel%). Abortando. ***
exit /b %errorlevel%

:fim
endlocal
