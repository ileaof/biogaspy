# BioGasSim

Simulador científico de **upgrading de biogás** (remoção de CO₂) em Python, modular,
orientado a objetos e de código aberto. Projeto, análise e comparação de processos de
purificação para produção de biometano a partir de biogás **47% CH₄ / 53% CO₂**.

> **Status (v0.1):** fundação arquitetada + extensível. Water Scrubbing e MEA totalmente
> funcionais (validados); DEA/MDEA/Selexol/Rectisol/PSA/Membranas como modelos
> simplificados/extensíveis. GUI e export PDF/VTK/Tecplot = roadmap.

## Instalação

```bash
pip install -e .            # ou: pip install -r requirements.txt
```

Requer Python ≥ 3.10, numpy, scipy, matplotlib, pandas.

## Uso rápido (CLI)

```bash
python -m biogassim.cli run-water          # lavagem com água (20 bar)
python -m biogassim.cli run-mea           # lavagem química com MEA (2 bar)
python -m biogassim.cli run-psa           # PSA (estimativa)
python -m biogassim.cli run-membrane      # membrana (1 estágio)
python -m biogassim.cli compare           # tabela comparativa + gráficos
```

Resultados e gráficos são salvos em `examples_output/`.

## Uso como scripts

```bash
python -m biogassim.Examples.WaterScrubbing
python -m biogassim.Examples.MEA
python -m biogassim.Examples.CompareAll
```

## Uso programático

```python
from biogassim.UnitOperations import Stream, Absorber, AbsorberSpec
from biogassim.Solvents import WaterSolvent

species = ["CH4", "CO2", "H2O"]
gas = Stream.make(species, [0.47, 0.53, 0.0], flow=100.0, T=298.15, P=20e5, "vapor")
solv = Stream.make(species, [0.0, 0.0, 1.0], flow=10000.0, T=293.15, P=20e5, "liquid")
spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                    T_op=293.15, pressure=20e5, height=15.0)
r = Absorber(gas, solv, WaterSolvent(), spec).solve()
print(r.purity_CH4, r.methane_recovery, r.CO2_removal, r.diameter)
```

## Arquitetura

```
biogassim/
  Core/             constantes, unidades, solver numérico, convergência
  Thermodynamics/   EOS (Peng-Robinson, SRK), Lei de Henry, fugacidade, flash
  Properties/       banco de componentes (CH4, CO2, H2O, N2, H2S, MEA, DEA, MDEA)
  MassTransfer/     difusão, teoria dos dois filmes, correlações (Re, Sc, Sh, HTU/NTU)
  Hydraulics/       recheios, flooding, perda de carga, diâmetro
  UnitOperations/   Absorbedor (estágios de equilíbrio), Stripper, Compressor, ...
  Solvents/         água (físico), MEA/DEA/MDEA (químico), Selexol, Rectisol
  PSA/              isoteras (Langmuir/Toth), ciclo PSA
  Membranes/        permeabilidades, modelo solução-difusão
  Optimization/     energia, economia, sensibilidade
  Export/           CSV, JSON, Excel, HTML (+ stubs PDF/Tecplot/VTK)
  Reporting/        gráficos (matplotlib)
  Examples/         casos prontos
  cli.py            linha de comando
tests/              pytest
docs/               documentação
```

Ver `docs/ARCHITECTURE.md` e `docs/ROADMAP.md`.

## Tecnologias implementadas

| Tecnologia | Estado | Observação |
|---|---|---|
| Water Scrubbing | ✅ funcional | alta pressão, água recirculada |
| MEA (amina química) | ✅ funcional | baixa pressão, reboiler |
| DEA / MDEA | ~ modelo | parâmetros de literatura; validar |
| Selexol / Rectisol | ~ modelo | solventes físicos (Henry) |
| PSA | ~ estimativa | isoterma + seletividade; ciclo dinâmico = roadmap |
| Membranas | ~ 1 estágio | solução-difusão; multi-estágio = roadmap |

## Validação

Sanity checks contra literatura: solubilidade de CO₂ em água a 25 °C
(0.034 mol/(L·atm)), fatores de compressibilidade (Z) via Peng-Robinson e fechamento
de balanço de massa do flash e do absorvedor (ver `tests/`). Validação sistemática
contra Aspen Plus/DWSIM é meta futura (ROADMAP).

## Licença

MIT.