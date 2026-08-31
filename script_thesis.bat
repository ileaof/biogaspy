@echo off
setlocal
REM ============================================================
REM  script_thesis.bat -- fluxo MEA da tese (BioGasSim)
REM  Cria o projeto, ajusta a composicao do feed e roda a
REM  varredura de composicao exportando para Excel.
REM ============================================================

echo(
echo [1/3] Criando projeto MEA (thesis_mea)...
biogassim new thesis_mea --tech mea
if errorlevel 1 goto :erro

echo(
echo [2/3] Definindo composicao do feed (CH4=0.5592 CO2=0.4407)...
biogassim set CH4=0.5592 CO2=0.4407 --case thesis_mea/case.json
if errorlevel 1 goto :erro

echo(
echo [3/3] Varredura de composicao CH4=0.40:0.70:0.05 -^> thesis.xlsx ...
biogassim sweep CH4=0.40:0.70:0.05 --out thesis_mea/thesis.xlsx
if errorlevel 1 goto :erro

echo(
echo Concluido. Saidas: thesis_mea\case.json e thesis.xlsx
goto :fim

:erro
echo(
echo *** ERRO na etapa anterior (errorlevel %errorlevel%). Abortando. ***
exit /b %errorlevel%

:fim
endlocal
