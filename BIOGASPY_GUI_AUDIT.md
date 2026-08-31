# AUDITORIA E MODERNIZAÇÃO DA GUI — BioGasPy

Data: 2026-08-30 · Escopo: auditoria completa da GUI, modernização arquitetural,
testes e documentação. Requisito central preservado durante todo o trabalho:
**a GUI e a CLI usam exatamente o mesmo backend científico** — nenhum cálculo
científico foi duplicado ou reescrito dentro da GUI.

---

## GUI STATUS

### Estado anterior (auditado)

| Componente | Avaliação |
|---|---|
| `comparison_tab.py` | **BOM — preservado** (614 linhas intocadas, exceto 2 linhas). Worker em `QThread` cancelável, progresso incremental, ciência 100% via `biogassim.comparison`, scrolls independentes por sub-aba. |
| `main_window.py` (antiga) | Deficiente: 2 abas, execução de simulação **bloqueante** (congelava a janela), sem menu/toolbar/barra de status, sem gerenciamento de projeto, sem marcação de resultado obsoleto, exceções cruas ao usuário. |
| Lógica de composição | **Boa — preservada** verbatim (redistribuição entre os outros dois componentes, presets, normalização). |
| Segurança H₂S | Existia cálculo via `biogassim.safety`, sem classificação visual PASS/WARNING/FAIL. |

### Estado atual (pós-modernização)

Janela principal profissional com **8 abas-alvo**:

1. **Projeto** — novo/abrir/salvar/salvar como, informações do projeto.
2. **Alimentação & Condições** — editor de composição (presets, redistribuição),
   propriedades de leitura (massa molar, LHV, PCI, orvalho, Wobbe) alimentadas
   pelo backend (`Properties.mixture_properties_general`).
3. **Lavagem de Gás** — operacionais editáveis (P, L, estágios, altura, V),
   tecnologia (água/MEA), **segurança H₂S com estados PASS/WARNING/FAIL**.
4. **Resultados do Processo** — chip de estado (READY/RUNNING/CONVERGED/
   WARNING/FAILED/OUTDATED), tabela científica de métricas, **log do solver
   colapsável**.
5. **Comparação de Processos** — preservada, recebe linhas compartilhadas.
6. **Desempenho & Economia** — 6 seções (Desempenho, Energia, Dimensionamento
   hidráulico, Água, Economia, Qualidade do gás tratado) + resumo da comparação.
7. **Estudos Paramétricos** — 7 estudos, gráfico matplotlib, exportações.
8. **Relatórios** — exportação JSON/CSV/HTML/XLSX via backend (`Export.py`).

Infraestrutura: menu (Arquivo/Simulação/Ferramentas/Exibir/Ajuda), toolbar
(Executar/Parar), barra de status com chip de estado + contexto
("Executando scrubbing de água | Iteração … | Residual …"), atalhos
(Ctrl+N/O/S, F5, Ctrl+Q), arquivos recentes (QSettings), tema claro/escuro
persistente, geometria da janela persistente.

---

## COMPLETED IMPROVEMENTS

### Arquitetura modelo–vista (nova camada `biogassim/gui/`)

- **`state.py`** — `AppState(QObject)`: hub de sinais
  (`feed_changed`, `metrics_ready`, `comparison_ready`, `solver_log`,
  `project_dirty`, `error`), máquina de estados READY/RUNNING/CONVERGED/
  WARNING/FAILED/OUTDATED com paleta visual (`state_css`). Nenhuma ciência.
- **`workers.py`** — `FunctionWorker` e `ParametricWorker` (QThread,
  canceláveis entre pontos, sinal `point` em streaming); `friendly_error()`
  converte exceções em mensagens de usuário (nunca traceback cru).
- **`project.py`** — `ProjectManager`: dirty tracking, recents (QSettings,
  máximo 10), I/O 100% delegado em `biogassim.cases.save_case/load_case`.
- **`tabs.py`** — classes de vista puras: `ProjectTab`, `FeedTab`, `GasWashingTab`,
  `ResultsTab`, `PerformanceTab`, `ParametricTab`, `ReportsTab` (+ constantes e
  `wrap_scroll`). A lógica de composição da alimentação foi migrada **verbatim**
  da janela antiga.
- **`main_window.py`** — controladora: monta abas, menus, toolbar, status bar;
  fachadas de compatibilidade (`spins`, `sliders`, `table`, `feed_conditions()`,
  `run_case_blocking()`) para os testes existentes.
- **`qt.py`** — shim PySide6/PyQt5 (QObject, Qt, QSettings, Signal, QAction
  handling, exec compatível).

### Execução não-bloqueante

- `Executar caso` roda `cases.run_case` em `FunctionWorker`; a GUI permanece
  responsiva, status bar mostra RUNNING, chip CONVERGED/FAILED ao final.
- Parâmetros: `ParametricWorker` com progresso incremental e cancelamento.
- `run_case_blocking()` existe **apenas** para testes (bombeia eventos com
  `processEvents`; não é usado no fluxo interativo).

### Marcação de resultados obsoletos (stale)

- Qualquer edição de alimentação/operacionais → estado **OUTDATED**:
  banner na aba Resultados, tabela em itálico/cinza, sincronizado com
  Desempenho/Comparação (que mostram aviso de desatualização).

### Segurança H₂S

- Estado visual PASS/WARNING/FAIL calculado exclusivamente com
  `biogassim.safety` (`h2s_warnings`, `engine_suitable`,
  `set_max_h2s_treated_ppm`): PASS = adequado a motor/gasoduto; WARNING = t_H2S
  dentro da banda de tolerância (limite>0); FAIL = acima do limite do usuário.
- Aviso permanente de gás tóxico/corosivo quando há H₂S no feed, **antes** de
  qualquer simulação.

### Projeto = format `case.json` da CLI

- Salvar/abrir usa o mesmo serializador da CLI — um projeto salvo na GUI abre
  com `biogasim run case.json` e vice-versa (testado por paridade).
- Detecção de não-salvo no fechamento (Salvar/Descartar/Cancelar).

### Preservações deliberadas (seção 45 do prompt)

- `comparison_tab.py`: mantido, com 2 linhas adicionadas
  (`comparison_finished` signal + emit) para integrar ao novo estado.
- Lógica normalização composição, cálculos de propriedades, dimensionamento
  hidráulico, economia: todas continuam chamando o backend — **zero cálculo
  científico novo dentro de classes de GUI**.

---

## REMAINING ISSUES

1. **Bug de ambiente PySide6 em pytest**: acessar
   `menuBar().actions()[i].menu()` dentro de pytest/offscreen retorna wrapper
   shiboken "already deleted" (reproduzível com QMainWindow mínimo, fora do
   BioGasPy). Contornado armazenando referências diretas aos menus
   (`window.m_file` etc.) — não afeta a aplicação real.
2. **Log do "Varredura de H₂S"** no menu Simulação roda de forma bloqueante
   (bombeia eventos) porque reaproveita `run_sweep_blocking`; ideal mover para
   worker dedicado.
3. `HELP.html` precisa de atualização com capturas das novas abas
   (`docs/capture_gui.py` pronto para regenerar imagens).
4. Diálogos de Relatórios/Estudos usam `QFileDialog` nativo — em empacotamentos
   one-file pode valer a pena forçar diálogo não-nativo.
5. Tradução/pt-BR já consistente, mas strings de QSettings não versionadas
   (mudança de chave invalidaria preferências locais do usuário).

---

## TEST STATUS

| Suite | Resultado |
|---|---|
| `tests/test_gui.py` (novo, reescrito) | **32 passed** |
| `tests/test_comparison.py` + `tests/test_h2s_ternary.py` (GUI antiga) | **71 passed** |
| Suíte completa (`pytest tests`) | **324 passed** |
| `ruff check biogassim tests` | limpo |

Cobertura dos novos testes (headless, `QT_QPA_PLATFORM=offscreen`):

- 8 abas-alvo presentes e títulos corretos.
- Menus Arquivo/Simulação/Ferramentas/Exibir/Ajuda + ações do Arquivo +
  Sobre + Manual HTML; toolbar e barra de status.
- **Cada aba com QScrollArea independente** (Comparação via sub-abas).
- Composição: redistribuição, presets, H₂S → estados de segurança
  (WARNING antes de rodar, PASS após, FAIL com limite 0).
- `feed_conditions()` fonte única (usada por backend, comparação, estudos).
- Execução em thread: tabela populada, estado CONVERGED, mensagem de convergência.
- Stale: OUTDATED após editar feed (itálico na tabela), limpo após reexecução.
- Projeto: salvar/carregar ida-e-volta **compatível com CLI**, abrir projeta
  defaults, arquivos recentes registrados.
- Desempenho populado e resumo de comparação compartilhado.
- Estudos paramétricos: 3 pontos H₂S, varredura de P_bar 4 pontos,
  cancelamento de worker, export CSV.
- **Paridade numérica GUI ≡ CLI** (purity/recovery/total_kW/custo específico
  com rel=1e-9) e mesmo `ComparisonEngine`.
- Fluxo completo ponta-a-ponta de 19 passos (projeto→feed→operacionais→execução
  thread→obsoletência→reexecução→comparação→desempenho→estudo→exportações).

---

## CLI/GUI CONSISTENCY

- **Mesmo backend**: GUI chama apenas `biogassim.cases` (`run_case`,
  `sweep_h2s`, `frange`, `TECHNOLOGIES`, `DEFAULT_OPERATING`, `Case`),
  `biogassim.comparison` (`ComparisonEngine`, `export_comparison`),
  `biogassim.Properties`, `biogassim.safety`, `biogassim.Export`.
  **Nenhum cálculo científico na camada de vista.**
- **Mesmo formato de projeto**: `case.json` compartilhado — verificado por
  teste (`cases.load_case` lê o que a GUI salvou).
- **Paridade numérica**: teste automático garante métricas idênticas
  (rel=1e-9) entre GUI e CLI para o mesmo caso.
- **CLI intacta**: todos os subcomandos (`run`, `compare`, `sweep`, …)
  preservados; 324 testes, incluindo os 292 pré-GUI, seguem passando.

---

## RECOMMENDED NEXT STEPS

1. **Worker para varredura H₂S do menu** (remover o bloqueio restante).
2. **Regenerar `docs/images`** com `docs/capture_gui.py` e atualizar
   `HELP.html` (novas abas, estados visuais, segurança H₂S).
3. **Empacotamento** (`pyproject.toml` entry point `biogassim_gui`) e ícone.
4. **Internacionalização**: extrair strings p/ `.ts` se houver demanda de
   versão em inglês.
5. **Diálogos de erro** com detalhes expandíveis (traceback opcional em
   modo desenvolvedor).
6. CI: adicionar a suíte GUI ao pipeline (requer libgl1/fontes no runner,
   offscreen).