# BIOGASPY — PRODUCTION READINESS AUDIT

**Data:** 2026-08-30 · **Versão auditada:** v0.2 (commit `e67a932`, branch `main`)
**Método:** inspeção de 100% do pacote `biogassim/` (26 módulos core + GUI/CLI/Examples),
execução da suíte de testes, varredura de robustez de 220 casos, estudos de sensibilidade,
cálculos independentes de verificação (dew point, Wobbe, densidade da água, propriedades via API).
**Tolerância de balanço de massa adotada nesta auditoria:** ε_mass ≤ 1e-6 (relativa).

---

## 1. Executive Summary

O BioGasPy é um **simulador de pesquisa** com núcleo numérico genuinamente robusto
(absorvedor de estágios de equilíbrio com Newton global, 253 testes passando,
termodinâmica de referência correta) — **mas não é, na versão atual, uma ferramenta
de dimensionamento para construção de planta real**. A conclusão do roteiro:

> **PRODUCTION READY: NO.**
> Pode ser usado *parcialmente* como base de triagem (screening) e estudo conceitual,
> mas **não** para dimensionar e construir um lavador real sem as correções e
> complementos listados nos itens 13–17.

Os três motivos estruturais (além dos bugs pontuais):

1. **O fluxograma é só o absorvedor**: `compressor (1 estágio ideal) → coluna → fim`.
   Não há regeneração do solvente (flash multiestágio/stripper), recuperação de CH₄
   do off-gas, KO drum, demister, intercoolers, secagem ou sistema de alívio.
2. **O gás tratado é, por construção, anidro** (H₂O não-volátil, K≡0): o simulador
   é **matematicamente incapaz** de prever a saturação de água real do biometano
   na depressurização — etapa obrigatória antes do motor-gerador.
3. **A economia trata solvente circulante como consumido** (água ~2.300 m³/h
   lançadas como consumo), distorcendo o USD/Nm³ e o ranking comparativo
   — a própria métrica que a ferramenta anuncia.

Bugs confirmados por execução: `import` circular em `Thermodynamics` (quebra se
importado antes de `Properties`), densidade da água **crescente com T**
(1.001,45 kg/m³ a 90 °C vs 965,3 real), tensão superficial 3×, Wilke de mistura ~6×
abaixo, NRTL com índices transpostos, entalpia de flash adiabático sem calor latente,
linha "Rectisol" da comparação que na verdade roda Selexol a 298 K.

---

## 2. Software Architecture

### 2.1 Mapa (26 módulos core, ~9.600 linhas)

```
Core/          constants (SI), units (vestigial, nunca usado), solver (Newton/Broyden/GMRES), convergence
Properties/    components (12 comps, Shomate/DIPPR), GasProperties (PCI/PCS), Water, Amines,
               Mixtures, Methane/CarbonDioxide (código morto)
Thermodynamics/ eos (cúbica base), PengRobinson, SRK, Fugacity, Henry, Interactions (kij),
               Flash (RR+SS), ActivityModels (NRTL quebrado, eUNIQUAC stub)
Solvents/      base, Water (Henry), Selexol/Rectisol, MEA/DEA/MDEA + KentEisenberg (especiação iônica)
UnitOperations/ base (Stream), Absorber (MESH tridiagonal), Stripper (não usado), Auxiliaries
               (cooler/pump/flash_drum/heat_exchanger — não usados), Compressor
Hydraulics/    Packing (13 recheios, Fp + Stichlmair C1/C2/C3), Flooding (GPDC/Eckert), PressureDrop (Stichlmair 1989)
MassTransfer/  TwoFilmTheory, FilmTheory, Correlations (Onda-Rocha, Bravo), Diffusion (Fuller, Wilke-Chang)
PSA/           Adsorption (isotermas), Regeneration (stub)
Membranes/     MembraneModel (solution-diffusion, 1/2 estágios/série), Permeability
Optimization/  Economics, Energy, Sensitivity
Comparison/CLI/GUI  comparison.py (9 tecnologias), cli.py (18 subcomandos), gui/ (PySide6)
tests/         20 arquivos, 253 testes — todos passando em 23,5 s
```

### 2.2 Achados arquiteturais

- **Backend único CLI↔GUI: confirmado.** Ambos importam `cases.py`/`Examples`/`ComparisonEngine`;
  não há replicação de cálculo científico. (Divergências de caso: GUI fixa T=298,15 K e
  rodízio H₂S forçado em "water" — `main_window.py:428,480`.)
- **Código funcional jamais invocado:** `Stripper`, `pump`, `cooler`, `flash_drum`,
  `heat_exchanger`, `units.py`, NRTL (`ActivityModels`), `Methane.py`/`CarbonDioxide.py`
  → a planta está faltando *não por falta de código*, mas por falta de **montagem do
  fluxograma** (a exceção é o stripper de água, que realmente não existe — o existente é de vapor, para aminas).
- Sem TODOs críticos pendentes; todos os stubs são documentados
  (`e_uniquac_stub`, ciclo Skarstrom do PSA, exporters PDF/Tecplot).
- `Stream.__post_init__` normaliza Σz=1 (§2 do roteiro: normalização ✓; validação de
  composições negativas ausente — z<0 entra silenciosamente).

---

## 3. Thermodynamic Audit

| Item | Status | Evidência |
|---|---|---|
| Peng–Robinson | ✅ correta | PR-78, α de Soave-Kwak, mistura vdW quadrática, lnφ_i padrão; Z(CH₄, 300 K, 10 bar)=0,9786 vs exp ≈0,982 |
| SRK | ✅ correta (com kij do PR sem reespecificação) | coefs. padrão; verificação manual dos coeficientes |
| Z | ✅ analítico, 3 raízes, guardas | heurística de fase rudimentar (1 raiz → vapor se Z>0,4) — ok p/ biogás, frágil perto do crítico |
| Fugacidade | ✅ | `f = z·φ·P`; sem Poynting (doc promete, código não implementa) |
| Regra de mistura | ✅ vdW clássica | sem regras avançadas (não esperado) |
| kij CH₄–CO₂ | ✅ 0,0919 | valor canônico (simuladores/Knapp-Dohrn) |
| kij CH₄–H₂S | ✅ 0,0825; CO₂–H₂S 0,0974 | valores plausíveis, mas **citação genérica**, sem fonte por par |
| kij ausentes | ⚠️ 10 pares (H₂/H₂O/CO/CO₂/N₂/O₂/Ar/NH₃ entre si) e todas as aminas = **0,0 silencioso** | `get_kij(...,0.0)` |
| Henry CO₂/CH₄/H₂S–H₂O | ✅ bateram Sander | 0,034 / 0,0014 / 0,10 mol/(L·atm) a 25 °C; van't Hoff com ΔH adequado |
| Flash VLE | ✅ RR+SS com K de EOS | sem teste de estabilidade (tangent-plane); fallback `converged=True` em fase simples |
| Kent-Eisenberg | ⚠️ calibrado vs Jou/Aronu (fator ≤5) | **validade α≲0,55**; pCO2(α=0,7)=3,7 MPa (salto não físico); H₂S em aminas usa Henry físico **independente de T** → prevê slip quase total de H₂S (fisicamente errado) |

**Veredito termodinâmico:** EOS/Henry sólidos e suficientes para a **região de operação**
de water scrubbing (5–30 bar, 283–313 K). Pontos fracos: `import` circular (`eos.py:20`),
Poynting prometido e não implementado, kij silenciosamente zero, validade docum. do
Kent-Eisenberg limitada. Para a rota água, a termodinâmica **não é o gargalo**.

---

## 4. Mass-Transfer Audit

- **Modelos presentes mas desconectados do dimensionamento.** Two-film (`overall_Ky/Kx`,
  composição interfacial), Onda-Rocha (k_L), Bravo (k_G), Fuller, Wilke-Chang, Hatta
  (fator E) existem; **o Absorvedor é de estágios de equilíbrio** e não os usa para
  resolver a coluna.
- **HTU/NTU/KLa são diagnósticos invertidos**: NTU é calculado *a posteriori* dos
  perfis de equilíbrio (força motriz log-média) e `KLa = V/A·NTU/Z` extrai-se do
  próprio Z escolhido pelo usuário — **a altura não resulta de NTU×HTU nem de KLa**;
  quem define a altura é o usuário (`height=None` → coluna sem altura ⇒ sem NTU/HTU/KLa).
  Para projeto de coluna realista faltaria K_Ya *a priori* (fatores E, área molhada,
  correlações de Billet/Stichlmair-Bravo-Fair) — hoje só o esqueleto existe.
- k_G/k_L individuais: disponíveis via `Correlations`, mas nenhum caminho de cálculo
  os usa; `stage_efficiency` (Murphree) assume K_Ya = 1 com unidade inconsistente
  (`Ng = Kya·a·Z/G` — K_Ya é adimensionalizado errado).
- Sem HETP funcional real (`HETP_from_HTU` nunca chamado). Sem wetting/área interfacial
  efetiva. Sem modelo rate-based.
- **H₂O nunca é volátil** (ver §8): o balanço de água da coluna é impossível no modelo.

---

## 5. Hydraulic Audit

- **Recheios:** 13 tipos (13 pares a/ε/Fp + constantes Stichlmair), valores típicos de
  Billet/Kister coerentes (ex.: Pall 50: a=110 m²/m³, ε=0,96, Fp=66 1/m ≈ valores de
  catálogo). Aviso de documentação para validar com fornecedor — postura correta.
- **Flooding:** GPDC/Eckert com curva de flood exponencial calibrada "dentro de ~20%"
  do gráfico para ar/água (docstring honesta). Fração de flooding fixa em 70%
  (`operating_velocity(u_flood, 0.7)`) — valor industrial razoável, mas rígido
  (não recalcula se o diâmetro é imposto).
- **ΔP:** Stichlmair-Bravo-Fair (1989) com holdup h_L=0,555·Fr^⅓ e limite h_L→ε.
  Implementação correta e reduz-se à seca quando h_L→0. ⚠️ o ΔP calculado **nunca
  retroalimenta** o perfil de pressão da coluna (P uniforme; comentário do spec diz
  o contrário — `Absorber.py:42,163`).
- **Densidade do gás no sizing usa MM médio não-ponderado incluindo H₂O/amina**
  (`Absorber.py:510-514`): erro parcialmente cancelante em D via u_flood, mas enviesando
  flooding/ΔP; para biogás a 20 bar, subestima u_flood em ~8% e o diâmetro em ~4%
  (na direção perigosa: coluna menor).
- En trainment/weeping: N/A para recheio (correto); load point não é calculado.
- Holdup: só o pré-loading; sem hidrodinâmica de loading/fregmentação.

---

## 6. Energy Audit

- **Balancos:** massa fecha em 1e-15 (precisão de máquina, verificado em 220 casos);
  **energia não há verificação global** — o balanço por estágio (adiabático) usa CMO
  simplificado com calor de absorção; o modo isotérmico (default) **silencia** o calor
  de absorção (T fixo): para CO₂/água o aquecimento adiabático real seria relevante.
- **Compressor:** 1 estágio isentrópico ideal-gás, k=1,31 fixo, η=0,75. O exemplo injeta
  no absorvedor gás a **705,8 K** (20:1 em um estágio), resfriado "por suposição"
  (T_op=isotérmico). Sem intercooler, sem aftercooler, sem duty atribuível.
- **Bomba:** nunca usada; o exemplo calcula bombeamento inline (P·Q/η) — unidades corretas.
- **Regeneração:** termo fixo 4,0 MJ/kg CO₂ (regua de bolso para aminas); água = 0.
- **Flash adiabático:** entalpia sem termo latente → fiscalmente quebrado (bug confirmado).
- Comparação com literatura (Persson et al. 2006; Bauer et al. 2013): water scrubbing
  real consome 0,25–0,35 kWh/Nm³ a 8–11 bar; o modelo deu **0,554 kWh/Nm³** — ~1,7×
  maior, **explicável** (compressão a 20 bar em 1 estágio, L/V=100, sem intercooler,
  sem creditos de recuperacao de CH₄). Consistente dadas as premissas, não validado
  no ponto realista.

---

## 7. H₂S Audit

- **Componente independente: sim**, em toda a pilha (banco de componentes, Henry próprio
  H=5,63e7 Pa ≡ 0,10 mol/(L·atm), absorção multicomponente, kij CH₄–H₂S e CO₂–H₂S).
- **Remoção modelo:** entrada 1% H₂S → saída ~0,00003 ppm (equilíbrio, água fresca).
  Fisicamente coerente para água fresca em uma passada (H₂S é ~3× mais solúvel que CO₂),
  mas **otimista para plantas reais** que recirculam água regenerada por flash (a água
  residual retarda a absorção de H₂S; plantas water-scrub costumam precisar de
  polimento com carvão/Fe-Oₓ). O modelo não representa nem o recirculado nem o polimento.
- **Sensibilidade varrida:** CLI sweep H₂S existe (0–1%); caso 1% H₂S → perda CH₄
  ligeiramente reduzida, remoção H₂S integral.
- **Defeito em aminas:** K(H₂S) físico e fixo (ver §3) — para MEA/DEA/MDEA o H₂S
  deveria ter quimissorção; hoje o módulo de aminas não serve para sour service.

---

## 8. Equipment Audit

**Presente no fluxograma executado (o único caminho real):** compressor 1 estágio → absorvedor recheado.

**Implementado e nunca chamado:** `flash_drum` (PR, funcional), `cooler`,
`heat_exchanger`, `pump` (placeholder), `Stripper` (vapor, para aminas).

**Ausente — lista explícita (§14 do roteiro):**

| Equipamento | Estado no código | Necessário para water scrubbing? |
|---|---|---|
| KO drum / demister de entrada | ausente | CRÍTICO (biogás bruto é úmido) |
| Filtro de partículas/espuma | ausente | alto |
| Compressor multistágio + intercoolers | ausente (1 estágio ideal) | alto |
| Separador de condensado pós-compressão | ausente | alto |
| **Regeneração do solvente (flash 2-3 estágios + reciclo)** | **ausente** (flash_drum existe, sem montagem) | **CRÍTICO** |
| Compressor de reciclo do off-gas (recup. CH₄) | ausente | CRÍTICO |
| Stripper a ar/vácuo p/ água | ausente | alto |
| Tanque de circulação / buffer | ausente | alto |
| Cooler de solvente (rejeitar calor de absorção) | ausente | alto |
| Purga/tratamento de efluente | ausente | CRÍTICO (água carregada de CO₂/H₂S/CH₄) |
| Desumidificador (TSA/glicol) pós-letdown | ausente | **CRÍTICO p/ motor** (ver §10) |
| Filtro final, odorização, skid de injeção | ausente | médio/alto |
| PSVs, flare, vent, interlocks, ESD | ausente | CRÍTICO (ver §9) |
| Medição de vazão/nível/instrumentação | ausente | alto |

---

## 9. Safety Audit

- `safety.py`: consultivo, apenas H₂S — limites corretos (IDLH 50 ppm NIOSH,
  TLV 1 ppm ACGIH, motor 10 ppm, pipeline 4 ppm); aviso de toxicidade no feed,
  verificação de compliance do produto, alerta IDLH. Sem riscos de CH₄/LEL,
  asfixia, sobrepressão, corrosão, estática — **nada implementado**; sem flare/PSV/ESD
  (não é obrigação de um simulador, mas não há *nem checklist*).
- ⚠️ limite global mutável (`set_max_h2s_treated_ppm`) — estilo não-reentrante.
- ⚠️ conversão heurística fração↔% (≤1 → ×100) ambígua exatamente em valores=1.
- Veredicto: adequado como *aviso*, insuficiente como *base de segurança*.
- Corrosão (§19): nada no código; ambiente CO₂+H₂S+H₂O+wet CO₂ é corrosivo
  (sour service, NACE MR0175) — **não modelável nem alertado pelo simulador**;
  os avisos de segurança não citam materiais.

---

## 10. Engine-Gas Quality Audit

**Calculado** (`cases._treated_gas_quality`): CH₄/CO₂, H₂S ppm, PCI/PCS, Wobbe, densidade, Z.
**Checado contra especificação: só H₂S.** Ausentes os checks de pureza mínima, banda
de Wobbe, pressão/temperatura de entrega, e **umidade**.

- **Umidade (estrutural):** o gás tratado sai anidro por construção (H₂O K≡0).
  Cálculo independente desta auditoria: gás saturado após letdown de 20 bar →
  1 bar a 20 °C carrega **~18.800 mg H₂O/Nm³** (~1,9% vol? não: 2,34% vol → veja tabela abaixo),
  contra specs típicas de motor/grid de ≤60–100 mg/Nm³ (DIN 51624 ≤200 mg/Nm³):

  | T após letdown, P=1 bar | y_H2O saturado | mg H₂O/Nm³ |
  |---|---|---|
  | 12 °C | 1,40% | ~11.300 |
  | 20 °C | 2,34% | ~18.800 |
  | 30 °C | 4,25% | ~34.100 |

  ⇒ **sem secador, o biometano do simulador violaria qualquer especificação de
  motor 100-300×** — e o simulador não pode nem vê-lo. Gap crítico.
- **Wobbe (verificado):** biometano 97% → Wobbe 50,5 MJ/Nm³, PCI 34,7 (na banda de
  gás natural 48–53); 90% CH₄ → 44,3 MJ/Nm³ (fora). Coerente.
- Propriedades avaliadas sempre a 298,15 K, independente da T real de saída.

---

## 11. Validation Status

| Ponto | Comparação | Resultado |
|---|---|---|
| Z PR (CH₄/CO₂) | gás ideal e não-ideal moderado | ✔ <1% |
| Psat CO₂ @ 253 K por inversão de fugacidade | 19,6 bar | ✔ 19,55 (<1%) |
| Henry CO₂/CH₄/H₂S/N₂ @ 25 °C | Sander 2015 | ✔ exato (0,034/0,0014/0,10/0,0006) |
| Kent-Eisenberg pCO2(α) 30% MEA 40 °C | Aronu 2011 | ✔ dentro de fator 5 (α≤0,55) |
| Balanço de massa | máquina | ✔ 1e-15 em 227 casos |
| Consumo específico de energia | lit. 0,25–0,35 kWh/Nm³ (8–11 bar) | ⚠️ 0,554 a 20 bar/1 estágio — explicável |
| Fração de flooding GPDC | gráfico Eckert (ar/água) | ±20% (autodeclarado), sem dados externos |
| Perda de CH₄ | lit. 2–4% (recirculação c/ recuper.) | ⚠️ 7,3% aqui (sem regeneração/recup.) |
| Solubilidades em coluna real / pilot | **nenhum dado experimental de coluna** | ✘ não validado |
| Perda de carga / flooding de coluna real | nenhum | ✘ não validado |

**Varredura de robustez (220 casos aleatórios, P 4–30 bar, T 283–313 K, L/V 30–200,
N 6–20, 5 recheios, com/sem H₂S):** 0 NaN/Inf, 0 frações negativas ou >1, 0 fluxos
negativos, 0 aquecimentos não físicos. **7 casos (3,2%) não convergiram** (padrão:
L/V alto + muitos estágios + recheio de alta área) — o resultado é retornado como
"aproximado", mas **um deles quebrou o balanço (4,5e-6)**: casos não-convergentes
não devem ser exportados como válidos sem flag visível nas saídas.

**Composições obrigatórias do roteiro (20 bar, L/V=100, N=12, Pall 50):**

| Feed | Conv. | Pureza CH₄ | Recup. CH₄ | Remoção CO₂ | H₂S saída | ε_mass | CH₄ dissolvido |
|---|---|---|---|---|---|---|---|
| 47/53 | ✔ | 99,9994% | 92,74% | ~100% (6,4 ppm) | — | 1,9e-15 | 3,44 mol/s |
| 47/52/1% H₂S | ✔ | 99,9994% | 92,68% | ~100% (6,1 ppm) | ~0 ppm | 2,0e-15 | +H₂S 0,010 mol/s |
| 60/39,5/0,5% | ✔ | 99,996% | 93,44% | 99,99% (42 ppm) | ~0 ppm | 5,6e-16 | 3,93 mol/s |
| 70/29,8/0,2% | ✔ | 99,99% | 93,83% | 99,97% | ~0 ppm | 1,5e-15 | 4,32 mol/s |

A **perda de CH₄ é calculada explícita e honestamente** (§6 do roteiro: OK — nunca 100%,
de 92,7% a 93,8% de recuperação nestes pontos, monótona com L/V).

---

## 12. Missing Features (resumo §22, §23)

- Regeneração/reciclo (flash multiestágio + recuperador de CH₄ + compressor de reciclo).
- Modelo de umidade/dew point/secagem; H₂O volátil na coluna.
- Rate-based mass transfer (ou ao menos K_Ya a priori e design de altura).
- Intercooler/aftercooler e condensado pós-compressão.
- BOP completo (KO drum, demister, filtros, tanque, purga, PSVs).
- Especificação completa de combustível (spec-check engine, não só H₂S).
- Comparação justa: feed T/P atualmente ignorada pelos adaptadores; H₂S descartado
  para aminas/PSA/membranas; **"Rectisol" roda Selexol a 298 K** (bug);
  solvente circulante contabilizado como consumo; `run` e `compare` produzem USD/Nm³
  diferentes para o mesmo caso físico (rubricas distintas).
- PSA: ciclo Skarstrom real (hoje equilíbrio estimado + recuperação fixa 95%) —
  não é instrumento de comparação quantitativa.
- Corrosão/materiais/sour service: fora do escopo, sem sequer avisos.

---

## 13. Risk Matrix (matriz de gaps)

| # | Requisito | Status | Implementado | Validado | Falta | Risco | Prioridade | Ação |
|---|---|---|---|---|---|---|---|---|
| 1 | Termodinâmica CH₄/CO₂/H₂O | OK | ✔ | ✔ (lit.) | — | baixo | — | manter |
| 2 | Henry H₂O | OK | ✔ | ✔ | Poynting | baixo | LOW | implementar Poynting p/ alta P |
| 3 | kij documentados por par | Parcial | ✔ | parcial | fontes por par | médio | MEDIUM | citar fonte por linha |
| 4 | Import circular | **Bug** | — | — | fix | médio | **CRITICAL** | mover `Component` p/ módulo folha |
| 5 | Água: ρ(T), σ(T) | **Bug** | — | — | correção Kell/σ | médio | **CRITICAL** | corrigir `Properties/Water.py` |
| 6 | Wilke / NRTL | **Bug** (mor.) | — | — | reescrever | baixo (não usados) | HIGH | corrigir antes de expor API |
| 7 | Convergência (3% dos casos) | Parcial | ✔ | flag | robustez L/V alto | médio | HIGH | continuar com Broyden/damping; marcar resultados |
| 8 | Transferência de massa rate-based | Ausente | esqueleto | ✘ | K_Ya/área molhada/E | alto | **CRITICAL** p/ dimensionamento | integrar Onda/Bravo/Billet ao design da coluna |
| 9 | ΔP retroalimenta P da coluna | Ausente | — | — | acoplar | médio | HIGH | acoplar ΔP por estágio |
| 10 | Regeneração + recup. CH₄ | Ausente | ✘ | ✘ | flash/stripper/reciclo | alto | **CRITICAL** | montar fluxograma com `flash_drum`+compressor reciclo |
| 11 | Umidade/dew point/secagem | Ausente | ✘ | ✘ | H₂O volátil + letdown flash | alto | **CRITICAL** p/ motor | modelo de saturação + dryer |
| 12 | BOP (KO, demister, filtros) | Ausente | ✘ | ✘ | equipamentos | médio | HIGH | unidade stubs → integração |
| 13 | Spec motor (Wobbe, pureza, T/P) | Parcial | parcial | parcial | spec-check completo | médio | HIGH | `engine_spec` com bandas |
| 14 | Economia (água/solvente circ.) | **Bug** | ✔ | ✘ | split consumo/purga | alto | **CRITICAL** | separar circulação × make-up; incluir CAPEX |
| 15 | Comparação justa (feed T/P, H₂S) | Parcial | parcial | ✘ | harmonizar | médio | HIGH | passar feed real p/ todos os adaptadores; fixar Rectisol |
| 16 | Validação c/ dados de coluna | Ausente | ✘ | ✘ | dados exp./piloto | alto | **CRITICAL** p/ certificar nível 3+ | benchmark c/ DWSIM/Aspen + piloto |
| 17 | Segurança além de H₂S | Ausente | parcial | ✘ | LEL/pressão/checklist | médio | MEDIUM | ampliar `safety.py` |
| 18 | Instrumentação/controle | Ausente | ✘ | ✘ | — | baixo p/ sim | LOW | fora do escopo simulador |

---

## 14. Production Readiness Classification

> **LEVEL 2 — Research Simulator** (bem acima de protótipo educacional, claramente
> abaixo de "engenharia validada").

Justificativa:

- **Não é Level 1:** núcleo numérico robusto (Newton global), 253 testes de unidade e
  de validação contra literatura, balanço de massa exato, backend único, CLI+GUI+batch+sweep.
- **Não é Level 3:** sem validação contra nenhum dado experimental de coluna, sem
  regeneração, com bugs de propriedade de água confirmados, sem rate-based, sem
  ferramental de umidade; casos não-convergentes podem ser exportados como válidos.
- Distâncias para Level 3 (simulador validado): itens 1, 4–7 e 16 da matriz.
- Distâncias para Level 4/5 (suporte a projeto piloto/produção): itens 8–12, 14.

---

## 15. Recommended Improvements (priorizados)

**CRITICAL (bloqueiam uso de engenharia):**
1. Corrigir `Properties/Water.py` (ρ de Kell 1975, σ por Tr=T/Tc) e o import circular — <1 dia.
2. Montar o fluxograma completo: `compressor → (cooler) → absorvedor → flash 2-3 estágios
   (+ compressores de reciclo p/ CH₄) → stripper a ar/vácuo → recirculação com purga`.
   O `flash_drum` já existe; é **montagem**, não ciência nova.
3. H₂O volátil na coluna (Henry p/ água em mistura, ou flash de saturação na saída)
   + cálculo de dew point pós-letdown + duty de secador.
4. Corrigir economia: separar água circulante × make-up/purga; corrigir `Rectisol`;
   harmonizar `run` × `compare`.

**HIGH:**
5. Acoplar transferência de massa real (K_Ya por Onda/Bravo/Billet, E(Hatta), área
   molhada) para dimensionar altura — hoje o usuário "adivinha" a altura.
6. Convergência: fallback Broyden/SS estendido p/ L/V alto; nunca exportar caso
   não-convergente sem flag destacada em CSV/JSON/relatório.
7. `engine_spec` completo: bandas de Wobbe/pureza/H₂S/H₂O/T/P com pass/fail.
8. Fixar `ComparisonEngine`: feed T/P real para todos; corrigir Rectisol; H₂S em todas
   as rotas (ou remover da comparação).

**MEDIUM/LOW:**
9. ΔP por estágio acoplado; 10. Poynting; 11. fontes por par de kij; 12. expandir safety
(LEL/pressão, checklist de planta); 13. CAPEX simples (módulos de custo por equipamento).

---

## 16. Validation Plan

1. **Termodinâmica:** VLE CH₄–CO₂ (TRC/RK datasets, 5–40 bar, 220–290 K); solubilidades
   3 gases × 5 temperaturas (Sander); expansão p/ H₂S–H₂O (Sander/Barrett) já coberto.
2. **Coluna:** comparar com pontos de full-scale publicados (Persson 2006; Bauer 2013:
   pureza, perda CH₄, consumo de água e 0,25–0,35 kWh/Nm³ nos pontos corretos de
   P/L — validar também a faixa de circulação de água do modelo, ~12–80 L/Nm³).
3. **Benchmark DWSIM/Aspen:** mesmo caso (47/53, 20 bar, L/V=100, 12 estágios): Z,
   K_CO2 e recuperação de CH₄ dentro de ±10%; investigar desvios (esperados nos
   coeficientes de transferência).
4. **Hidráulica:** ΔP e u_flood de piloto ou dados de fornecedor (Sulzer/Koch) para 2 recheios.
5. **Regeneração:** validar flash pós-coluna contra simulação Aspen/DWSIM do mesmo caso.

---

## 17. Roadmap to Production

- **PHASE 1 — Verificação científica (1–2 semanas):** bugs 1/5/6 da matriz (água,
  import, Wilke/NRTL), Poynting, MM ponderado no sizing, ΔP acoplado, flags de
  não-convergência nas saídas.
- **PHASE 2 — Validação (2–4 semanas):** planos §16.1–16.3; tabelas de validação
  automatizadas no CI.
- **PHASE 3 — Projeto de engenharia (1–2 meses):** fluxograma completo com
  regeneração/reciclo (item 2), umidade/secante (item 3), rate-based K_Ya,
  `engine_spec`, economia corrigida + CAPEX.
- **PHASE 4 — Verificação piloto:** comparar com dados de planta piloto real
  (ΔP, pureza, perda CH₄); refinar recheio/fator de flooding.
- **PHASE 5 — Industrial:** integração COMOS/SmartPlant style (fora do escopo),
  HAZOP support, materiais/corrosão, interface de dados de planta.

---

## 18. Final Recommendation

- **§32 — "Pode o BioGasPy, na versão atual, ser usado diretamente para dimensionar
  e construir um lavador real?" → NO.**
  A termodinâmica CH₄/CO₂/H₂S–água é correta e o balanço de massa fecha, mas o
  dimensionamento resultante (a) omite a regeneração e a recuperação de CH₄,
  (b) não pode prever a umidade do gás (etapa obrigatória p/ motor), (c) não
  dimensiona a altura por transferência de massa (o usuário fixa a altura), e
  (d) contém bugs confirmados em propriedades de água usadas na hidráulica.
- **Como base de estudo conceitual, varredura de composições e comparação
  relativa (com ressalvas): YES, parcialmente.**
- **§36 — Não confundir:** mesmo após as fases 1–3, BioGasPy será um **suporte a
  projeto**, não um projeto executivo; não substitui normas (NR-10/13, NACE MR0175,
  ABNT/ISO gás), análise de risco formal (HAZOP/LOPA), certificação de equipamentos
  nem comissionamento.

**CURRENT STATUS:** Level 2 (Research Simulator); 253/253 testes; 220/220 casos sem
NaN/negativos; 7 (3,2%) não convergem; balanço de massa 1e-15 nos convergentes.

**PRODUCTION READY: NO** — parcialmente utilizável para screening (ver §18).

**CRITICAL MISSING ITEMS:** regeneração do solvente + recuperação de CH₄; modelo de
umidade/desumidificação; dimensionamento por taxas de transferência (altura real);
correção de propriedades de água + import circular; economia de circulação × consumo;
validação com dados experimentais de coluna.

**VALIDATION REQUIRED:** VLE CH₄–CO₂ vs dados; comparação com plantas full-scale
(publicadas); benchmark DWSIM/Aspen; dados de fornecedor p/ flooding/ΔP.

**RECOMMENDED NEXT STEP:** Phase 1 (correções de bugs, ~1–2 dias de trabalho:
`Water.py`, import circular, MM ponderado no sizing, flags de convergência nas
saídas) e, em seguida, montar o fluxograma de regeneração com o `flash_drum` já
existente + compressor de reciclo — a mudança de maior impacto físico por esforço.
---

## ADENDO — Fase 1 executada (2026-08-30)

Correções da Fase 1 do roadmap implementadas e travadas por 26 testes de
regressão (`tests/test_phase1_regression.py`; suíte completa: 274 passando):

| Item | Ação |
|---|---|
| Import circular `Thermodynamics` ↔ `Properties` | imports lazy em `GasProperties.py`; teste subprocess trava |
| Densidade da água (ρ crescia com T; Bigg válido só ≤40 °C) | polinômio grau 6 à tabulação Kell 1975 (0–100 °C, err. máx. 0,012 kg/m³) |
| Tensão superficial da água ~3× alto | Vargaftik correta: σ(25 °C)=0,0720 N/m |
| Wilke com denominador errado (μ 6× baixo) | φ_ij por par, somatório por componente (RPP 9-5.12) |
| NRTL com índices τ/α transpostos | Renon-Prausnitz correto; ponto binário manual + Gibbs-Duhem diferencial |
| Sinal ΔH dissolução (`Methane.py`) | consistente com van't Hoff do banco Henry |
| `pump()` com ρ implícita falsa | parâmetro `rho` explícito (default 1000 kg/m³) |
| MM não-ponderada no sizing | média ponderada pela composição local |
| Sem rastreabilidade de balanço | `mass_balance_error` em `AbsorberResult` (≈1e-15) e nas métricas/comparação |
| GPDC extrapolado silenciosamente (X≈23–33 no water scrubbing) | física mantida; `flood_parameter_X`, `gpdc_extrapolated`, alerta em `message`, `Hydraulics.is_gpdc_valid()` |

**Status honesto:** a extrapolação do GPDC em cargas líquidas altas foi
*exposta*, não resolvida — dimensionamento por capacidade líquida nesses
regimes permanece Fase 3 do roadmap. Diâmetro/ΔP de water scrubbing com
(L/V) molar ≳ 60 NÃO devem ser usados para projeto. Nenhum modelo científico
correto foi alterado; a classificação do simulador (nível 2 — pesquisa) e o
veredito **PRODUCTION READY: NO** permanecem até Fases 2–5.
