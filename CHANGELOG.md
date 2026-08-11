# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- **H₂S como primeira extensão do modelo binário CH₄–CO₂.** H₂S integrado
  ponta-a-ponta como componente de alimentação (CH₄ + CO₂ + H₂S = 100%),
  sem liberar outras espécies além das já suportadas:
  - **Banco de parâmetros de interação binária (kij)** não-nulos para
    Peng-Robinson (`Thermodynamics/Interactions.py`): CH₄–CO₂≈0,092,
    CH₄–H₂S≈0,083, CO₂–H₂S≈0,097 (+ demais pares). `kij_matrix(species)` injetada
    em todas as instanciações de PR (`GasProperties`, `Auxiliaries`); antes tudo
    era zero. O banco é editável/atualizável em um único local.
  - **Qualidade do gás tratado** (`cases._treated_gas_quality`): composição real
    do gás de topo (CH₄/CO₂/H₂S), LHV/HHV/Wobbe/densidade/densidade relativa/Z
    via PR multicomponente, **concentração residual de H₂S** (mol% e ppm) e
    **carregamento de H₂S na fase líquida** (mol H₂S/mol solvente).
  - **Segurança H₂S** (`biogassim/safety.py`): avisos de toxicidade/corosividade
    distinguindo feed / gás tratado / fase líquida; **limite máximo admissível
    de H₂S no gás tratado configurável** (default 10 ppm; motor/gasoduto);
    decisão explícita `engine_suitable` — o simulador **nunca** classifica
    silenciosamente gás com H₂S significativo como adequado para motor.
  - **Varredura paramétrica de H₂S** (`cases.sweep_h2s` + CLI `sweep H2S=...`):
    varia H₂S de 0 a 5 mol% mantendo a razão CH₄:CO₂, coletando remoção de H₂S,
    recuperação de CH₄, remoção de CO₂, consumo de água/energia, altura e
    qualidade do gás tratado.
  - **Dashboard de resultados** (`biogassim/dashboard.py`): saída no formato
    feed / upgraded / performance / gas quality / safety, reusada por `run` e
    `report` na CLI.
  - **CLI**: `set` aceita H₂S (e qualquer espécie cadastrada) com verificação
    do total = 100%; `run`/`report` ganham `--max-h2s-ppm`.
  - **GUI**: editor de composição **ternário** CH₄/CO₂/H₂S (spin + slider +
    presets, normalização que redistribui o restante preservando a razão dos
    outros dois), banner de segurança de H₂S, tabela de resultados com remoção
    de H₂S e H₂S no gás tratado, e mapa de desempenho vs H₂S.
  - **Testes** (`tests/test_h2s_ternary.py`, 29): kij não-nulos, normalização
    ternária, solubilidade H₂S, qualidade do gás tratado, segurança, dashboard,
    CLI `set`/`sweep` H₂S, e **regressão §17** — H₂S=0 reproduz o binário dentro
    de 1e-9. Total: 199 testes.

### Adicionado
- **Absorção de gases ácidos no water scrubbing** (multi-gás): a água agora
  absorve CO₂, **H₂S** (≈3× mais solúvel, removido preferencialmente) e **NH₃**,
  enquanto N₂/O₂/H₂/Ar/CO passam praticamente direto. Dados de Henry para
  O₂/H₂/Ar/CO/NH₃ em água; `WaterScrubbing.run_case` monta o conjunto de espécies
  a partir da composição do feed e reporta a remoção por espécie
  (`H2S_removal`, `NH3_removal`, ...); `cases`/`batch` propagam a composição
  completa para a água. Aminas (MEA) reativas com H₂S/NH₃ = roadmap.
  `tests/test_acidgas.py` (9).
- **Estudos paramétricos multivariável + otimização** (`biogassim/studies.py` +
  CLI `sensitivity`/`optimize`): superfícies de resposta 1-D/2-D sobre qualquer
  combinação de composição (`CH4`) e variáveis operacionais (`P_bar`,
  `L_over_V`, `N_stages`, `height_m`, `flow_mols`), com o conjunto completo de
  métricas; heatmap/curva em PNG. `optimize` faz busca em grade sob restrições
  (objetivo min/max com constraints de pureza/recuperação/etc.) a partir de um
  JSON de especificação.
- **Composição multicomponente** (`Properties/GasProperties.py`): a alimentação
  não é mais restrita a CH₄–CO₂. Suporta qualquer subconjunto de CH₄, CO₂, N₂,
  O₂, H₂, H₂O, H₂S, NH₃, CO, Ar (H₂/NH₃/CO/Ar adicionados ao banco de
  componentes). Entrada em fração molar/mássica/volumétrica ou vazão molar/
  mássica (`to_mole_fractions`), com normalização e validação. `mixture_
  properties_general`/`GasMixture` dão MM, Z, densidade, LHV/HHV, Wobbe e SG de
  qualquer mistura — validados vs. literatura (ar: MM 28.97, Z≈1; H₂: ~120 MJ/kg).
- **Simulação em lote** (`biogassim/batch.py` + CLI `batch`): lê um CSV de
  composições e avalia todas de uma vez (propriedades por feed; com `--tech`,
  roda o upgrading sobre a subcomposição CH₄/CO₂ e reporta a fração inerte).
- CLI `props` generalizado para qualquer mistura, com `--basis`.
- **GUI (Milestone 1)** (`biogassim/gui/`): interface gráfica desktop com shim de
  binding (PySide6 preferido, PyQt5 alternativo). Editor interativo de composição
  (spin/slider/presets, normalização e fração complementar em tempo real, leituras
  contínuas de propriedades), painel operacional, controles do solver + monitor de
  convergência, dashboard de resultados e gráfico de desempenho vs. composição.
  Comando `biogassim gui`; extra `pip install -e ".[gui]"`. Smoke tests headless
  (offscreen) em `tests/test_gui.py` (5).
- **Milestone 1 — CH₄–CO₂**: motor de composição e propriedades de gás
  (`Properties/GasProperties.py`): normalização/validação da composição binária
  e cálculo de massa molar, Z (Peng-Robinson), densidade real e normal, LHV/HHV
  (por mol, Nm³ e kg), Índice de Wobbe e densidade relativa ao ar — validados
  contra literatura (CH₄ puro: HHV ~39,8 MJ/Nm³, Wobbe ~53,5, LHV ~50 MJ/kg).
- **Modelo de casos** (`biogassim/cases.py`): caso em JSON (composição, vazão,
  tecnologia, condições), criação/carregamento/validação de projetos, execução
  com **composição variável** e **varredura paramétrica** da fração de CH₄.
- **CLI expandida**: `new`, `run`, `set` (com fração complementar automática),
  `props`, `sweep`, `export` (xlsx/csv/json) e `report` (HTML).
- Campo `flooding_fraction` (margem de inundação) exposto no `AbsorberResult` e
  nas métricas; `composition` opcional nos exemplos Water/MEA e em `biogas_stream`.
- **Membranas multi-estágio** (`biogassim/Membranes/`): modelo de mistura
  completa que **resolve** o corte de estágio θ a partir da área e das pressões
  (modo *rating*) ou dimensiona a área para um corte-alvo (modo *design*);
  `two_stage_recycle` (dois estágios com reciclo do permeado — configuração
  padrão de biometano, resolvida por Wegstein) e `series_stages` (cascata de N
  estágios em série). Permeância (permeabilidade / espessura) adicionada a
  `MembraneMaterial`. Exemplo `MembraneMultiStage`, comando de CLI
  `run-membrane-multi` e `tests/test_membrane.py` (10 testes).
- Configuração de lint (`ruff`) e cobertura (`pytest-cov`) em `pyproject.toml`.
- Integração contínua (GitHub Actions): lint + testes em Python 3.10–3.12.
- Arquivo `LICENSE` (MIT), `CHANGELOG.md` e `.gitattributes`.

### Alterado
- Exemplo de membrana de 1 estágio agora usa o modo *design* (a **área** é
  resultado calculado, não mais um valor fixo ignorado).
- Versão agora é fonte única em `biogassim/version.py` (pyproject usa `dynamic`).
- Anotações de tipo modernizadas para sintaxe PEP 585/604 (`list[...]`, `X | None`).

### Corrigido
- Exemplo de código no README (`Stream.make(...)` tinha argumento posicional após
  argumentos nomeados — `SyntaxError`).
- Remoção de código morto (variáveis atribuídas e nunca usadas) em `solver`,
  `Absorber`, `Compressor`, `Energy`, `MembraneModel`, `Regeneration` e exemplos.

## [0.2.0]

### Adicionado
- **Newton global no Absorbedor** (`method="newton"`, padrão): resíduo MESH
  consistente que converge em toda a faixa de L/V, incluindo o pinch onde o
  método sequencial (`method="ss"`, legado) divergia.
- **Especiação Kent-Eisenberg rigorosa** para MEA, DEA e MDEA (carbamato,
  bicarbonato, carbonato); β1/β2 calibrados vs. literatura.
- **Balanço de energia por estágio (modo adiabático)** com a "temperature bulge".
- **Estudo de sensibilidade paramétrica** (`Optimization/Sensitivity.py`):
  varreduras 1-D e 2-D (heatmap) sobre P, T, N estágios, altura e L/V.
- **Hidráulica de coluna rigorosa**: flooding via GPDC de Eckert e perda de carga
  via Stichlmair-Bravo-Fair; banco de recheios ampliado de 6 → 13.
- **Testes diretos** para `MassTransfer` e `Hydraulics` (antes sem cobertura).
- **Calibração VLE**: MDEA vs. Huttenhuis et al. (2007); solventes físicos
  Selexol/Rectisol vs. dados de solubilidade (Henni, Décultot, Leu & Robinson).
- Validação contra literatura em `tests/test_validation.py` (91 testes no total).

### Corrigido
- `MassTransfer/Diffusion.py`: Wilke-Chang (erro de unidade ×1e4) e Fuller
  (média harmônica → forma padrão).
- `PhysicalSolvents.py`: convenção de sinal do van't Hoff (T menor → mais solúvel).

## [0.1.0]

### Adicionado
- Fundação arquitetada e extensível: EOS cúbicas (Peng-Robinson, SRK), Lei de
  Henry, flash multicomponente, banco de componentes e misturas.
- Water Scrubbing e MEA funcionais ponta-a-ponta; DEA/MDEA/Selexol/Rectisol/
  PSA/Membranas como modelos simplificados.
- CLI (`biogassim`), exemplos executáveis, export CSV/JSON/HTML/Excel e gráficos.
- 21 testes pytest; `pip install -e .` e console-script funcionando.

[Não lançado]: https://github.com/
[0.2.0]: https://github.com/
[0.1.0]: https://github.com/
