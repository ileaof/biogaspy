# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado (unidades de vazão na GUI, 2026-09-01)

- **Seletor de unidade da vazão de alimentação** (`gui/tabs.py`): combo ao
  lado do campo "Vazão do biogás" com **mol/s** (SI, padrão), mol/h, kmol/s,
  kmol/h — fatores fixos — e **kg/h** e **Nm³/h** com fator *dinâmico*
  calculado pelo backend (`mixture_properties_general`: massa molar e
  densidade normal dependem da composição). Trocar a unidade preserva o valor
  físico; o caso (`case.json`) e a CLI continuam guardando sempre
  `flow_mols` em mol/s — a unidade é preferência de entrada/exibição.
- **Unidade espelhada nas demais abas**: `FeedTab.format_flow()` formata a
  vazão na unidade corrente; o cabeçalho "Flow" da sub-aba Configuração da
  Comparação (leitura, sempre herdada da alimentação) e a mensagem de status
  "Executando…" seguem a unidade escolhida. **Decisão:** a Comparação não tem
  vazão própria — comparação de métodos só faz sentido sob o mesmo feed
  (`--flow` permanece exclusivo da CLI).
- **Correção**: a varredura "Vazão de biogás" na aba Estudos Paramétricos
  lia `operating["flow_mols"]` (inexistente — `KeyError`); a base agora vem
  de `case.feed` (`gui/tabs.py`).
- **Testes**: 6 novos em `tests/test_gui.py` (conversão fixa/dinâmica,
  preservação do valor físico, round-trip de caso, grade da varredura,
  espelhamento no cabeçalho). Suíte completa: **330 testes passando**.

### Adicionado (modernização da GUI, 2026-08-30)

- **Arquitetura modelo–vista** (`biogassim/gui/`): `state.py` (`AppState`
  com sinais e estados visuais READY/RUNNING/CONVERGED/WARNING/FAILED/
  OUTDATED), `workers.py` (`FunctionWorker`/`ParametricWorker` executando
  ciência em QThread com cancelamento e `friendly_error`), `project.py`
  (`ProjectManager` com dirty tracking e arquivos recentes em QSettings),
  `tabs.py` (7 classes de vista puras) e `qt.py` (shim PySide6/PyQt5).
- **Janela principal profissional** (`main_window.py`): 8 abas-alvo (Projeto,
  Alimentação & Condições, Lavagem de Gás, Resultados do Processo, Comparação
  de Processos, Desempenho & Economia, Estudos Paramétricos, Relatórios),
  menus (Arquivo/Simulação/Ferramentas/Exibir/Ajuda), toolbar, barra de
  status com chip de estado, atalhos de teclado, tema claro/escuro e
  geometria persistentes.
- **Simulação não-bloqueante**: `run_case`/estudos em `QThread` — a janela
  permanece responsiva durante a iteração do solver.
- **Marcação de resultados obsoletos**: edição de alimentação/operacionais
  passa o projeto a OUTDATED (banner + tabela em itálico) até reexecução.
- **Segurança de H₂S visual**: classificação PASS/WARNING/FAIL na aba
  Lavagem de Gás, calculada exclusivamente por `biogassim.safety`.
- **Projeto = `case.json` da CLI**: salvar/abrir/recentes usam o mesmo
  serializador da CLI (`cases.save_case/load_case`) — um projeto salvo na
  GUI roda direto com `biogasim run case.json`.
- **`QScrollArea` independente por aba** (incluindo Desempenho & Economia);
  Comparação mantém as suas por sub-aba (componente preservado).
- **Suíte de testes da GUI** (`tests/test_gui.py`, 32 testes, offscreen):
  janela/menus/abas, composição, estados, obsoletência, projeto, segurança,
  estudos paramétricos canceláveis, **paridade numérica GUI ≡ CLI**
  (rel=1e-9) e fluxo ponta-a-ponta de 19 passos. Suíte completa: **324
  testes passando**; `ruff` limpo.
- **`BIOGASPY_GUI_AUDIT.md`**: relatório completo de auditoria (status,
  melhorias, pendências, testes, consistência CLI/GUI, próximos passos).

### Preservado

- `gui/comparison_tab.py` mantido (2 linhas de integração) — worker em
  thread e ciência via `biogassim.comparison` já estavam corretos.
- Lógica de composição (redistribuição/normalização) migrada verbatim.
- CLI inalterada; todos os cálculos científicos seguem no backend
  (`cases`, `comparison`, `Properties`, `UnitOperations`, `safety`, `Export`).

### Adicionado (auditoria de prontidão — Fases 2 e 3, 2026-08-30)

- **Correção de Poynting na fuga líquida** (`Thermodynamics/Henry.py`):
  Π = exp(v̄·(P − Psat,solvente)/RT) com volume molar parcial do gás dissolvido
  por espécie (CO2 34, CH4 37.5, N2 40.5, H2S 32, O2 31, H2 26.2, Ar 32,
  CO 33, NH3 24 cm³/mol). `K_value`/`K_values`/`x_eq` aceitam `poynting=True`;
  efeito ~2–3% a 20 bar (desprezível a 1 atm).
- **Validação multi-temperatura de H(T)** vs Sander (2015): dHsol/R do modelo
  (CO2 2405 K, CH4 1684 K, H2S 2526 K) contra série de Sander (2400/1900/2100 K)
  nas razões kH(313, 323 K)/kH(298 K) — desvios <1% (CO2), ~6% (CH4),
  ~10% (H2S), tolerâncias documentadas.
- **Testes estruturais two-film**: limites m→0 e m≫1 de K_y/K_x, consistência
  de fluxo interfacial (ky(y−yi)=kx(xi−x)), controle de filme líquido para
  CO2/água (m=H/P≫1 → Kx≈kx), monotonia do absorvedor em estágios e L/V.
- **Regeneração do solvente físico** (`UnitOperations/Regeneration.py`):
  água rica → flash 1 à média pressão (gás rico em CH4 recomprimido e
  devolvido à ALIMENTAÇÃO do absorvedor — arquitetura Wellmann) → flash 2 a
  ~1 atm (vent de CO2) → purge + makeup + bomba. Flash TP via Henry
  (Rachford-Rice, K_i = H_i/P; K_H2O = Psat/P). `strip_air=True` emula a
  coluna de dessorção varrida a ar (lean limpo; sem isso o x_CO2 residual de
  ~7e-4 fixa o topo em ~5% CO2). Loop feed+reciclo/solvente resolvido por
  ponto fixo em `Examples/WaterScrubbing.py` (converge em ~7-8 passes,
  contração ~x0.07) — a análise prévia de "divergência" era artefato do
  esquema amortizado de dois passes.
- **Secador TSA + umidade** (`Properties/Moisture.py`, `UnitOperations/Dryer.py`):
  Psat de água via Magnus-Tetens (Buck 1996, validado <0.5% em 10–60 °C),
  ponto de orvalho, conteúdo em mg/Nm³ (base úmida, 44.615 mol/Nm³ a STP) e
  secador a leito (remoção estequiométrica, duty ~4.5 MJ/kg H2O, ponto de
  orvalho de saída). Corrigido bug de base: especificação agora imposta na
  base úmida da SAÍDA (não da entrada).
- **Capacidade líquida no dimensionamento** (`Hydraulics/Packing.py`,
  `UnitOperations/Absorber.py`): com GPDC extrapolado (X≫2), o diâmetro passa
  a ser calculado por A = Q_L/j_L,máx (Kister; 0.020 m/s aleatório, 0.010–0.012
  estruturado) com flag `liquid_capacity_limited`.
- **Economia: circulação ≠ consumo de água**: `cases.py` agora cobra o
  makeup (purge + evaporação), não a circulação (L/V); métricas separadas
  `water_m3_per_h` (consumo) e `water_circulation_m3_per_h`. Ponto de orvalho
  e umidade do gás tratado reportados (`treated_H2O_mg_per_Nm3`,
  `treated_dew_point_C`).
- **Resultados do caso padrão (feed 47/53, 20 bar, L/V=100) com regeneração
  fechada**: pureza 100%, recuperação global 98.7%, reciclo 10.3 mol/s
  (23.7% CH4), CH4 devolvido 2.45 mol/s, perda no vent 0.65 mol/s, makeup
  13.0 m³/h (2% da circulação de 648.5 m³/h), 0.518 kWh/Nm³.
- Testes: +28 em `tests/test_phase2_phase3.py` (Poynting, Sander, two-film,
  regeneração com balanços, dryer/orvalho, capacidade líquida, economia).
  Suíte completa: **302 passando**.

### Corrigido (auditoria de prontidão para produção — Fase 1, 2026-08-30)
Auditoria completa em `BIOGASPY_PRODUCTION_READINESS_AUDIT.md` (classificação
nível 2 — simulador de pesquisa; **NÃO pronto para produção**). Correções da
Fase 1 do roadmap:

- **Import circular `Thermodynamics` ↔ `Properties`**: importar
  `biogassim.Thermodynamics` diretamente falhava com `ImportError`.
  Imports movidos para dentro das funções em `GasProperties.py`; travado por
  teste de regressão (`test_import_thermodynamics_first`).
- **Densidade da água** (`Properties/Water.py`): polynomial de Bigg válido só
  até 40 °C produzia ρ *crescente* com T (ρ(90 °C)=1001 kg/m³). Reajustado
  polinômio de grau 6 à tabulação de Kell (1975), 0–100 °C
  (ρ(25 °C)=997,05; ρ(90 °C)=965,5 kg/m³; erro máx. 0,012 kg/m³).
- **Tensão superficial da água ~3× alto** (0,216 → 0,0720 N/m a 25 °C):
  correlação de Vargaftik implementada corretamente.
- **Regra de Wilke** (`Properties/Mixtures.py`): acumulação denominador errada
  dava μ 6× baixo (90/10 CH₄/CO₂: 2,1e-6 → 1,13e-5 Pa·s). Implementação com
  φ_ij por par e somatório por componente (Reid-Prausnitz-Poling 9-5.12).
- **NRTL** (`Thermodynamics/ActivityModels.py`): índices τ/α transpostos;
  reescrito conforme Renon-Prausnitz, travado por ponto binário calculado à
  mão + consistência de Gibbs-Duhem diferencial.
- **Sinal do ΔH de dissolução** em `Properties/Methane.py` (consistente com o
  `HENRY_WATER` de van't Hoff).
- **Bomba** (`Auxiliaries.pump`): parâmetro `rho` explícito (default água
  1000 kg/m³); linha de ρ falsa removida.
- **Dimensionamento de coluna**: massa molecular do gás ponderada pela
  composição local (antes média aritmética não-ponderada das espécies).
- **Rastreabilidade**: `AbsorberResult` agora reporta `mass_balance_error`
  (precisão de máquina ~1e-15 em casos convergentes) e propaga para métricas/
  comparação; `metrics_from_absorber` inclui o erro e a flag de extrapolação.
- **Extrapolação do GPDC exposta** (não silenciada): water scrubbing com
  (L/V) molar=100 opera em X=(L/G)√(ρg/ρl)≈23–33, fora do gráfico de Eckert
  (X≲2). Física original mantida; adicionados `AbsorberResult.flood_parameter_X`,
  `gpdc_extrapolated` (bool) e mensagem de alerta explícita, além de
  `Hydraulics.is_gpdc_valid()`. Critério de capacidade líquida para essas
  cargas é trabalho da Fase 3 do roadmap (diâmetro/ΔP nesses regimes NÃO são
  confiáveis para projeto).
- **CLI de comparação em Windows**: subprocessos dos testes agora decodificam
  stdout como UTF-8 (codepage 1252 mojava o cabeçalho "COMPARAÇÃO").
- Testes: 26 novos de regressão em `tests/test_phase1_regression.py`
  (água/Kell, Wilke, NRTL, import circular, balanço de massa, GPDC, bomba).
  Suíte completa: **274 passando**.

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
