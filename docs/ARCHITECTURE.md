# Arquitetura do BioGasSim

## Visão geral

O BioGasSim é estruturado em pacotes com responsabilidades separadas, todos sob
`biogassim/`. O fluxo de cálculo de uma coluna é:

```
Componentes (Properties)  ──►  Termodinâmica (EOS / Henry / Flash)
                                         │
                                         ▼
        Solvente (Solvents)  ──►  Absorbedor (UnitOperations)
                                         │  usa
                                         ▼
                          Core.solver (Newton/Broyden/GMRES)
                                         │
                                         ▼
              MassTransfer + Hydraulics  ──►  dimensionamento / KLa / HTU/NTU
                                         │
                                         ▼
              Optimization (energia, economia) + Export + Reporting
```

## Núcleo numérico (`Core/solver.py`)

Métodos iterativos desacoplados das equações de processo:

- `newton_raphson(residual, x0, jacobian=None)` — Newton com damping, diferenciação
  numérica de fallback (custo N+1 avaliações) e limitação de passo.
- `broyden(residual, x0, J0=None)` — quase-Newton rank-1, útil quando a Jacobiana
  analítica não está disponível.
- `solve_sparse(matvec, b)` — GMRES via `scipy.sparse.linalg` para sistemas esparsos.

Controle de convergência em `Core/convergence.py` (`residual_norm`,
`relative_tolerance`, `wegstein`).

## Termodinâmica (`Thermodynamics/`)

- `eos.CubicEOS` — base abstrata: regras de mistura quadráticas (van der Waals com
  `k_ij`), cúbica em Z, coeficientes de fugacidade φ_i. Subclasses (`PengRobinson`,
  `SRK`) fornecem `a_c`, `b`, `alpha(T)`, `cubic_coeffs(A,B)` e `ln_phi(...)`.
- `Henry.HenryLaw` — equilíbrio gás-líquido via `p = H(T)·x` com van't Hoff; usado
  por Water Scrubbing e solventes físicos.
- `Flash.isothermal_flash` — Rachford-Rice + K-values da EOS (substituição sucessiva
  com detecção de fase única). `adiabatic_flash` — busca em T pelo balanço de entalpia.

## Absorvedor (`UnitOperations/Absorber.py`)

Modelo de **estágios de equilíbrio** com a matriz tridiagonal por componente
(método theta com atualização de vazões totais). Para cada estágio `j` e componente
`i`:

```
l_{i,j-1} - (1 + R_{i,j}) l_{i,j} + R_{i,j+1} l_{i,j+1} = 0
```

com `R_{i,j} = V_j·K_{i,j}/L_j`, `K` fornecido pelo solvente. Iteração:
resolve tridiagonal → atualiza `L_j = Σ l`, `V_j = Σ v` → recalcula `K` → repete,
com **trust-region** (limita a magnitude do passo) e relaxação adaptativa para
estabilidade perto do pinch. Convergência sobre os fluxos por componente.

O solvente fornece `K_value`, `heat_of_absorption` e propriedades da fase líquida
(ρ, μ, Cp), permitindo usar o mesmo motor para lavagem física (Henry) e química
(amina, K efetivo dependente do carregamento).

## Extensibilidade

### Novo solvente

Subclasse `Solvents.base.Solvent` implementando `K_value`, `heat_of_absorption`,
`density`, `viscosity`, `cp_liquid`, `molar_mass_liquid`, e defina `absorbed_species`
(e `amine_name` se reativo). O Absorbedor usa a interface automaticamente.

### Nova tecnologia de separação

- Baseada em coluna: reutilize `Absorber` com um novo `Solvent`.
- Não-coluna (PSA, membrana): crie o pacote (`PSA/`, `Membranes/`) com seu próprio
  modelo e um `run_case` em `Examples/` que devolva métricas padronizadas
  (`purity_CH4`, `recovery_CH4`, `CO2_removal`, `total_kW`, ...) — o `CompareAll`
  agrega automaticamente. O **iron sponge** (`UnitOperations/IronSponge.py` +
  `Examples/IronSponge.py`) segue este caminho: unidade de leito fixo
  (projeto estequiométrico, Ergun) registrada em `comparison.METHODS` com
  `category="adsorption"` e consumo de meio custado pela premissa
  `media_price_usd_per_t` (coluna `media_kg_per_yr`).

## Decisões de projeto

- Solver desacoplado das unidades (facilita reuso e teste).
- `Stream` dataclass imutável-em-essência (composição normalizada) como portador
  de correntes entre unidades.
- Backend matplotlib `Agg` (sem display) para geração de gráficos em lote/CLI.
- Exportação real em CSV/JSON; Excel via pandas/openpyxl (opcional); PDF/VTK/Tecplot
  como stubs documentados.