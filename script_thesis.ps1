# ============================================================
#  script_thesis.ps1 -- fluxo MEA da tese (BioGasSim)
#  Cria o projeto, ajusta a composicao do feed e roda a
#  varredura de composicao exportando para Excel.
# ============================================================
$ErrorActionPreference = 'Stop'

function Invoke-Step {
    param([string]$Titulo, [scriptblock]$Comando)
    Write-Host ""
    Write-Host $Titulo -ForegroundColor Cyan
    & $Comando
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "*** ERRO na etapa anterior (exit $LASTEXITCODE). Abortando. ***" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Invoke-Step "[1/3] Criando projeto MEA (thesis_mea)..." {
    biogassim new thesis_mea --tech mea
}

Invoke-Step "[2/3] Definindo composicao do feed (CH4=0.5592 CO2=0.4407)..." {
    biogassim set CH4=0.5592 CO2=0.4407 --case thesis_mea/case.json
}

Invoke-Step "[3/3] Varredura de composicao CH4=0.40:0.70:0.05 -> thesis.xlsx ..." {
    biogassim sweep CH4=0.40:0.70:0.05 --out thesis_mea/thesis.xlsx
}

Write-Host ""
Write-Host "Concluido. Saidas: thesis_mea\case.json e thesis_mea\thesis.xlsx" -ForegroundColor Green
