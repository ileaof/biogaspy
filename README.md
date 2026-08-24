# BioGasSim

Simulador científico de **upgrading de biogás** (remoção de CO₂) em Python, modular,
orientado a objetos e de código aberto. Projeto, análise e comparação de processos de
purificação para produção de biometano a partir de biogás **47% CH₄ / 53% CO₂**.

> **Status (v0.2):** 199 testes passando. Absorvedor com Newton global e balanço de
> energia adiabático; especiação **Kent-Eisenberg** rigorosa (MEA/DEA/MDEA); hidráulica
> de coluna (flooding de Eckert, perda de carga de Stichlmair); estudos de sensibilidade
> paramétrica; solventes físicos (Selexol/Rectisol) e MDEA calibrados vs. literatura;
> **membranas multi-estágio** (mistura completa, reciclo do permeado, cascata em série);
> **CLI de casos** (composição variável, varredura paramétrica); **GUI** (PySide6/PyQt5);
> e **composição multicomponente** (CH₄/CO₂/N₂/O₂/H₂/H₂O/H₂S/NH₃/CO/Ar) com propriedades
> de gás, simulação em lote e estudos paramétricos/otimização.
> **H₂S como primeira extensão do modelo binário CH₄–CO₂:** banco de **parâmetros de
> interação binária (kij)** não-nulos para Peng-Robinson (CH₄–CO₂, CH₄–H₂S, CO₂–H₂S),
> solubilidade de H₂S em água (≈3× mais solúvel que CO₂), qualidade do gás tratado
> (LHV/HHV/Wobbe/densidade/SG + H₂S residual), **segurança** (avisos de toxicidade,
> limite de H₂S configurável), **varredura de H₂S** e **dashboard** com seção H₂S.
> Water Scrubbing e MEA validados ponta-a-ponta (ver [`docs/ROADMAP.md`](docs/ROADMAP.md)).
> **Comparação de métodos:** `biogassim compare` (CLI) e a aba *Comparação de
> Métodos* da GUI rodam todas as tecnologias sob o mesmo feed via um backend
> compartilhado (`ComparisonEngine`) — tabela padronizada, ranking
> uni/multi-critério, energia/economia e exportação (CSV/JSON/HTML/XLSX/PDF).

## Clonar o repositório

Requer [Git](https://git-scm.com/) instalado.

```bash
git clone https://github.com/ileaof/biogaspy.git
cd biogaspy
```

Sem Git? Use **Code → Download ZIP** na [página do repositório](https://github.com/ileaof/biogaspy)
e extraia. Em seguida, siga a [Instalação](#instalação).

## Instalação

Recomenda-se um ambiente virtual:

```bash
python -m venv .venv
# Windows:        .venv\Scripts\activate
# Linux/macOS:    source .venv/bin/activate
```

```bash
pip install -e .              # instala o pacote + o comando `biogassim`
# extras opcionais:
pip install -e ".[gui]"       # interface gráfica (PySide6)
pip install -e ".[excel]"     # export para .xlsx (openpyxl)
```

Requer Python ≥ 3.10, numpy, scipy, matplotlib, pandas.

## Como iniciar

Após a instalação, a **linha de comando (CLI)** fica disponível de duas formas
equivalentes — use a que preferir:

```bash
biogassim <comando>            # comando de console (requer a pasta de scripts do
                               # Python no PATH)
python -m biogassim.cli <comando>   # sempre funciona, sem depender do PATH
```

Veja todos os comandos com `biogassim --help`. Para abrir a **interface gráfica
(GUI)**: `biogassim gui` (detalhes na seção [Interface gráfica](#interface-gráfica-gui)).

## Uso rápido (CLI)

```bash
python -m biogassim.cli run-water          # lavagem com água (20 bar)
python -m biogassim.cli run-mea            # lavagem química com MEA (2 bar)
python -m biogassim.cli run-psa            # PSA (estimativa)
python -m biogassim.cli run-membrane       # membrana (1 estágio)
python -m biogassim.cli run-membrane-multi # membrana multi-estágio (reciclo/série)
python -m biogassim.cli compare            # compara tecnologias (ver abaixo)
```

Resultados e gráficos são salvos em `examples_output/`.

### Comparação de métodos (CLI)

O comando `compare` roda várias tecnologias de upgrading sob a **mesma
alimentação** e devolve uma tabela padronizada (pureza, recuperação, remoção de
CO₂/H₂S, energia elétrica/térmica, consumo de água/solvente, OPEX, custo
específico, qualidade do gás tratado), ranking uni- e multi-critério e exportação.
É o mesmo backend (`biogassim.comparison.ComparisonEngine`) que a aba de
comparação da GUI — CLI e GUI produzem resultados numericamente idênticos.

```bash
biogassim compare                                # métodos recomendados, biogás 47/53
biogassim compare water mea psa membrane         # só os métodos informados
biogassim compare --case meu_projeto/case.json    # herda feed (composição/vazão) do caso
biogassim compare --mode optimized --flow 200    # modo otimizado (otimiza antes de rodar)
biogassim compare --export comparison.xlsx        # exporta relatório (.csv/.json/.html/.xlsx/.pdf)
```

Métodos disponíveis: `water`, `mea`, `dea`, `mdea`, `selexol`, `rectisol`,
`psa`, `membrane`, `membrane-multi` (alias: `multi`). Os marcados como
*Experimental* (DEA, Rectisol, PSA) são estimativas — aparecem, mas o conjunto
**Recomendados** traz apenas os operacionais e representativos.

Um método que falha (não converge/erro) é registrado como falha com a mensagem
do solver, sem cancelar a comparação — os demais métodos seguem e aparecem na
tabela.

### Casos e composição CH₄–CO₂ (Milestone 1)

Fluxo de trabalho baseado em *casos* (JSON) para estudar o efeito da composição
binária CH₄–CO₂ sobre desempenho, dimensionamento e economia:

```bash
biogassim new meu_projeto --tech water          # cria projeto + case.json padrão
biogassim set CH4=0.60 --case meu_projeto/case.json   # CO2 vira 0.40 (complemento)
biogassim set CH4=46 CO2=53 H2S=1 --case meu_projeto/case.json  # ternário CH4-CO2-H2S
biogassim run meu_projeto/case.json             # roda o caso, imprime dashboard
biogassim run meu_projeto/case.json --max-h2s-ppm 4   # impõe limite de H2S no tratado
biogassim props CH4=0.60 CO2=0.40 --P 20        # MM, Z, densidade, LHV/HHV, Wobbe, SG
biogassim sweep CH4=0.20:0.95:0.05 --out sweep.csv    # estudo paramétrico de composição
biogassim sweep H2S=0:0.05:0.005 --tech water   # varredura do contaminante H2S
biogassim export results.xlsx --case meu_projeto/case.json
biogassim report --case meu_projeto/case.json   # relatório HTML
```

A composição é sempre normalizada e validada. Para feed **binário** CH₄–CO₂ a
fração complementar é atualizada automaticamente (mexer no CH₄ atualiza o CO₂);
para feed **multi-espécie** (ex.: CH₄+CO₂+H₂S) todas as frações são
normalizadas para somar 100%. O `sweep` varre a fração de CH₄ (`CH4=...`) **ou**
do contaminante H₂S (`H2S=...`, mantendo a razão CH₄:CO₂) e tabela pureza,
recuperação, remoção de CO₂/H₂S, perda de metano, consumo de solvente/água,
energia, diâmetro/altura da coluna, perda de carga, margem de inundação, custo e
qualidade do gás tratado — a base dos mapas de desempenho.

### Misturas multicomponente e simulação em lote

A composição não é restrita a CH₄–CO₂: qualquer subconjunto dos gases
**CH₄, CO₂, N₂, O₂, H₂, H₂O, H₂S, NH₃, CO, Ar** é aceito (adicionar espécies é
só cadastrar em `Properties/components.py`, sem tocar no solver). A composição
pode ser dada em **fração molar, mássica ou volumétrica**, ou como **vazão molar
ou mássica** (`--basis mole|mass|volume|molar_flow|mass_flow`), sempre
normalizada.

```bash
biogassim props CH4=0.72 CO2=0.25 N2=0.03 --P 20    # propriedades de qualquer mistura
biogassim props CH4=0.5 CO2=0.5 --basis mass        # entrada em base mássica
biogassim batch feeds.csv --tech water --out results.csv   # centenas/milhares de feeds
```

O `batch` lê um CSV (uma linha por alimentação; colunas = espécies, + opcionais
`name`, `T_K`, `P_bar`, `basis`, `technology`) e calcula as propriedades de cada
mistura; com `--tech`, roda também o upgrading e reporta a remoção por espécie.

**Absorção de gases ácidos (water scrubbing):** a água absorve, além do CO₂, o
**H₂S** (≈3× mais solúvel — removido preferencialmente) e o **NH₃** (muito
solúvel), enquanto **N₂/O₂/H₂/Ar/CO** passam praticamente direto. A remoção é
reportada por espécie (`H2S_removal`, `NH3_removal`, `N2_removal`, …). O
**equilíbrio gás-líquido** usa Lei de Henry com dependência de temperatura (van't
Hoff); a **equação de estado** (Peng-Robinson) estende-se ao ternário CH₄–CO₂–H₂S
com **parâmetros de interação binária (kij) não-nulos** armazenados em
`Thermodynamics/Interactions.py` (CH₄–CO₂≈0,092, CH₄–H₂S≈0,083, CO₂–H₂S≈0,097).
A coluna resolve o transporte acoplado das três espécies ao longo dos estágios.

Após o upgrading, o simulador reporta a **qualidade do gás tratado**:
composição (CH₄/CO₂/H₂S), poder calorífico (LHV/HHV), Índice de Wobbe, densidade
e densidade relativa, além da **concentração residual de H₂S** (mol% e ppm) e do
**carregamento de H₂S na fase líquida** (mol H₂S/mol solvente). Nas **aminas
(MEA)**, a absorção **reativa** de H₂S/NH₃ ainda é roadmap — o modelo de amina
trata só CH₄/CO₂.

### H₂S — gás ácido tóxico e corrosivo

O **sulfeto de hidrogênio (H₂S)** está presente em praticamente todo biogás
(digestão anaeróbia de proteínas/sulfetos), tipicamente 50–4.000 ppm, podendo
chegar a % em aterros/corrosivos. É **altamente tóxico** (IDLH 50 ppm, TLV-TWA
ACGIH 1 ppm), **corrosivo** (ataca aço, concretos e lubrificantes) e odorante
(o limiar olfativo é ~0,0005 ppm, mas o olfato fadiga rapidamente em
concentrações maiores — o "silêncio" não significa segurança).

No **water scrubbing**, o H₂S é **mais solúvel em água que o CO₂** (H_H₂S < H_CO₂),
sendo removido preferencialmente no mesmo contato, mas parte acompanha o gás
tratado conforme a razão L/V e a pressão. O efeito sobre o processo:

- **Recuperação de CH₄** — levemente reduzida (a absorção de H₂S dilui o
  solvente e compete com CO₂, e algum CH₄ é co-absorvido).
- **Remoção de CO₂** — pouco afetada (H₂S é traço frente ao CO₂).
- **Equipamento** — o efluente líquido carregado de H₂S é **corrosivo** e exige
  *stripping* + tratamento antes do descarte/reuso; o gás tratado deve atender
  ao limite de H₂S do destino (motor ≤ ~10 ppm; gasoduto ≤ ~4 ppm).

**Segurança no simulador:** sempre que H₂S está presente na alimentação, o
software emite avisos distinguindo **feed / gás tratado / fase líquida**, e o
limite máximo admissível de H₂S no gás tratado é **configurável** (`--max-h2s-ppm`
na CLI, campo na GUI; `biogassim.safety.set_max_h2s_treated_ppm`). O simulador
**nunca** classifica silenciosamente um gás com H₂S significativo como adequado
para motor — a decisão `engine_suitable` é explícita.

### Estudos paramétricos e otimização

Superfícies de resposta (1-D ou 2-D) sobre qualquer combinação de **composição**
(`CH4`) e **variáveis operacionais** (`P_bar`, `L_over_V`, `N_stages`,
`height_m`, `flow_mols`), coletando o conjunto completo de métricas:

```bash
biogassim sensitivity L_over_V=40:120:20 --tech water --out curva.csv
biogassim sensitivity P_bar=5:30:5 --vary L_over_V=20:120:20 \
          --metric recovery_CH4 --out surf.csv --plot surf.png    # heatmap 2-D
```

A **otimização** faz busca em grade sob restrições (JSON de especificação):

```bash
biogassim optimize optimization.json --out best.json
```

```json
{
  "technology": "water",
  "objective": "specific_kWh_per_Nm3",
  "goal": "minimize",
  "variables": {"L_over_V": [40, 120, 40], "P_bar": [10, 25, 5]},
  "constraints": {"purity_CH4": [">=", 99.9], "recovery_CH4": [">=", 90]}
}
```

→ acha a condição de **menor energia específica** que satisfaz pureza ≥ 99,9% e
recuperação ≥ 90% (ex.: L/V=120, P=15 bar → 0,48 kWh/Nm³).

### Interface gráfica (GUI)

![Interface gráfica do BioGasSim: editor interativo de composição CH₄–CO₂, condições operacionais, resultados e mapa de desempenho](docs/images/gui.png)

Instale o extra da GUI (uma vez) e abra a janela principal:

```bash
pip install -e ".[gui]"        # instala PySide6 (alternativamente, tenha PyQt5)
biogassim gui                  # abre a janela principal
```

Três formas equivalentes de iniciar a GUI — use qualquer uma:

```bash
biogassim gui                  # comando de console
python -m biogassim.cli gui    # via a CLI (se `biogassim` não estiver no PATH)
python -m biogassim.gui.app    # inicia o pacote da GUI diretamente
```

Num desktop normal (Windows/macOS/Linux) a janela abre com fontes normais —
**não** defina `QT_QPA_PLATFORM=offscreen` (isso é apenas para testes headless).

#### Como usar a GUI

A GUI (PySide6 preferido, PyQt5 alternativo — via shim) é a camada interativa
sobre o mesmo motor de simulação da CLI. A janela tem cinco áreas (a aba
*Simulação* tem barra de rolagem própria, então todo o conteúdo permanece
acessível com a janela reduzida):

- **Condições operacionais** (topo, à esquerda) — escolha a **tecnologia**
  (`water` ou `mea`) e ajuste vazão do biogás, pressão, razão L/V, número de
  estágios e altura da coluna. Trocar a tecnologia carrega os valores padrão
  correspondentes.
- **Composição da alimentação** (meio, à esquerda) — defina a mistura
  **CH₄/CO₂/H₂S** por um **preset** (biogás 47/53/0, biogás c/ 1–5% H₂S,
  digestor 60/40, metano puro), pelos **campos numéricos em %** ou pelos
  **sliders**. A composição é normalizada: editar um componente redistribui o
  restante entre os outros dois preservando a razão atual (mexer no H₂S mantém a
  proporção CH₄:CO₂). O total é sempre mostrado e validado contra 100%. O bloco
  **Propriedades da mistura** recalcula em tempo real: massa molar, fator Z,
  densidade (a T,P) e normal, PCI/PCS (LHV/HHV), Índice de Wobbe e densidade
  relativa ao ar — agora incluindo a contribuição do H₂S.
- **Segurança H₂S** (logo abaixo da composição) — banner que acende sempre que
  há H₂S na alimentação (tóxico/corosivo), com o **limite máximo admissível de
  H₂S no gás tratado** configurável em ppm. Após *Executar caso*, mostra a
  concentração de H₂S no gás tratado, o carregamento líquido e a decisão de
  adequação para motor (SIM/NÃO).
- **Solver** (base, à esquerda) — **Executar caso** roda a simulação com a
  composição e as condições atuais; **Varrer H₂S** roda o estudo paramétrico do
  contaminante. A linha de status logo abaixo é o **monitor de convergência**
  (convergiu?, número de iterações, pureza e recuperação).
- **Resultados** (à direita) — tabela com pureza de CH₄, recuperação, remoção de
  CO₂, **remoção de H₂S** e **H₂S no gás tratado (ppm)**, perda de metano,
  consumo de solvente/água, energia, diâmetro e altura da coluna, margem de
  inundação, Wobbe do gás tratado e custo específico.
- **Mapa de desempenho** (base, à direita) — gráfico de remoção de H₂S,
  recuperação de CH₄ e remoção de CO₂ em função da fração de H₂S na alimentação.

**Fluxo típico de uso:**

1. Escolha a **tecnologia** no painel de condições operacionais.
2. Defina a **composição** (preset, campo `%` ou slider) — as propriedades da
   mistura são atualizadas a cada mudança; o banner de segurança acende se houver
   H₂S.
3. Ajuste as **condições operacionais** (pressão, L/V, estágios, altura).
4. Clique em **Executar caso** — as métricas aparecem na tabela de resultados, o
   status mostra a convergência e o banner de segurança atualiza com o H₂S
   tratado e a adequação para motor.
5. Clique em **Varrer H₂S** — o mapa de desempenho mostra como a remoção de H₂S, a
   recuperação de CH₄ e a remoção de CO₂ variam na faixa de 0–5 mol% de H₂S.

Todos os cálculos reutilizam o mesmo núcleo da CLI (`biogassim.cases`); portanto,
para as mesmas entradas, GUI e CLI produzem resultados idênticos.

#### Aba "Comparação de Métodos"

A janela principal tem **duas abas**: *Simulação* (acima) e **Comparação de
Métodos**. A segunda compara as tecnologias de upgrading lado a lado usando
o **mesmo backend** que `biogassim compare` (`biogassim.comparison.ComparisonEngine`)
— nenhuma termodinâmica é duplicada na GUI, apenas apresentação.

Para facilitar a visualização, a aba *Comparação de Métodos* é dividida em
**duas sub-abas**:

- **Configuração** — condições de alimentação herdadas (somente leitura),
  seleção de métodos, modo (Padrão/Otimizado), parâmetros por tecnologia e
  botões **Executar** / **Parar** / **Salvar config** / **Carregar config**.
- **Resultados** — tabela comparativa, gráfico de barras e ranking/decisão,
  com o botão **Exportar**. Ganha a tela inteira (em vez de dividi-la com os
  controles). Ao concluir a comparação a GUI troca automaticamente para esta
  sub-aba.

Cada sub-aba tem sua **própria barra de rolagem** (QScrollArea independente),
de modo que todo o conteúdo permanece acessível mesmo com a janela reduzida ou
com muitos métodos selecionados / muitos resultados exibidos.

**Sub-aba Configuração:**

- **Condições herdadas (somente leitura)** — a alimentação (CH₄/CO₂/H₂S, vazão,
  pressão, T, modelo termodinâmico) vem da aba *Simulação*, sem reentrada. Quando
  o feed muda, o cabeçalho é atualizado e os resultados anteriores ficam marcados
  como **desatualizados** (⚠ "Condições de alimentação alteradas — rode a
  comparação novamente").
- **Seleção de métodos** — *checkboxes* por tecnologia + botões *Selecionar
  tudo* / *Limpar* / *Recomendados*. Métodos experimentais aparecem rotulados.
- **Modo** — *Padrão* (parâmetros predefinidos) ou *Otimizado* (a engine otimiza a
  variável principal de cada tecnologia antes de rodar).
- **Parâmetros por tecnologia** — área expansível: cada método selecionado
  mostra seus parâmetros operacionais (água: P/L/V/N/altura; aminas: +concentração;
  PSA: adsorvente/pressões; membranas: material/pressões/área/estágios).
- **Execução** — roda em *thread separada* (a GUI continua responsiva), com
  botões **Executar** / **Parar** e um monitor de progresso por método
  (corrente / concluído / falhou). Um método que falha não derruba a comparação.
- **Salvar / Carregar config** — salva e recarrega a configuração de comparação
  (métodos, parâmetros, modo, pesos) em JSON. A configuração também viaja no
  arquivo de projeto (campo `comparison` do caso) quando salva pela CLI/`cases`.

**Sub-aba Resultados:**

- **Tabela de resultados** — uma linha por método, ~24 colunas (pureza,
  recuperação, remoção CO₂/H₂S, perda CH₄, vazão do produto, consumo de
  água/solvente, energia elétrica/térmica/total, energia específica, pressão de
  operação, altura/diâmetro da coluna, eficiência global, OPEX, custo específico,
  LHV/HHV/Wobbe do gás tratado, H₂S no gás tratado, convergiu), com ordenação e
  menu de visibilidade de colunas.
- **Gráfico comparativo** — barras por métrica (dropdown "Comparar por").
- **Ranking** — *melhor método por critério* + ranking **multi-critério ponderado**
  com pesos editáveis (pureza, recuperação, energia, custo, água).
- **Exportar** — exporta o relatório completo
  (.csv/.json/.html/.xlsx/.pdf); ao concluir a comparação a GUI troca
  automaticamente para esta sub-aba.

## Uso como scripts

```bash
python -m biogassim.Examples.WaterScrubbing
python -m biogassim.Examples.MEA
python -m biogassim.Examples.MembraneMultiStage   # 1 vs 2-estágios+reciclo vs série
python -m biogassim.Examples.CompareAll
```

## Uso programático

```python
from biogassim.UnitOperations import Stream, Absorber, AbsorberSpec
from biogassim.Solvents import WaterSolvent

species = ["CH4", "CO2", "H2O"]
gas = Stream.make(species, [0.47, 0.53, 0.0], flow=100.0, T=298.15, P=20e5, phase="vapor")
solv = Stream.make(species, [0.0, 0.0, 1.0], flow=10000.0, T=293.15, P=20e5, phase="liquid")
spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                    T_op=293.15, pressure=20e5, height=15.0)
r = Absorber(gas, solv, WaterSolvent(), spec).solve()
print(r.purity_CH4, r.methane_recovery, r.CO2_removal, r.diameter)
```

## Arquitetura

```
biogassim/
  Core/             constantes, unidades, solver numérico, convergência
  Thermodynamics/   EOS (Peng-Robinson, SRK), Lei de Henry, fugacidade, flash,
                    parâmetros de interação binária kij (Interactions.py)
  Properties/       banco de componentes (CH4, CO2, H2O, N2, H2S, MEA, DEA, MDEA)
  MassTransfer/     difusão, teoria dos dois filmes, correlações (Re, Sc, Sh, HTU/NTU)
  Hydraulics/       recheios, flooding, perda de carga, diâmetro
  UnitOperations/   Absorvedor (estágios de equilíbrio), Stripper, Compressor, ...
  Solvents/         água (físico), MEA/DEA/MDEA (químico), Selexol, Rectisol
  PSA/              isoteras (Langmuir/Toth), ciclo PSA
  Membranes/        permeabilidades, modelo solução-difusão
  Optimization/     energia, economia, sensibilidade
  Export/           CSV, JSON, Excel, HTML (+ stubs PDF/Tecplot/VTK)
  Reporting/        gráficos (matplotlib)
  Examples/         casos prontos
  cli.py            linha de comando
  cases.py          casos JSON, validação, execução, varreduras (CH4, H2S)
  comparison.py     ComparisonEngine — compara tecnologias sob o mesmo feed
                    (backend compartilhado por `biogassim compare` e pela GUI)
  safety.py         segurança H2S (avisos, limite configurável, adequação p/ motor)
  dashboard.py      formatação de resultados (feed/upgraded/performance/safety)
  gui/              GUI PySide6/PyQt5 (main_window + aba comparison_tab)
tests/              pytest
docs/               documentação
```

Ver [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) e [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Tecnologias implementadas

| Tecnologia | Estado | Observação |
|---|---|---|
| Water Scrubbing | ✅ funcional | alta pressão, água recirculada |
| MEA (amina química) | ✅ funcional | baixa pressão, reboiler; Kent-Eisenberg calibrado (Aronu 2011) |
| DEA / MDEA | ✅ / ~ | Kent-Eisenberg rigoroso; MDEA calibrado (VLE, Huttenhuis 2007), DEA a calibrar |
| Selexol / Rectisol | ✅ funcional | solventes físicos (Henry), calibrados vs. literatura |
| PSA | ~ estimativa | isoterma + seletividade; ciclo dinâmico = roadmap |
| Membranas | ✅ 1 e multi-estágio | mistura completa (resolve θ); 1 estágio, 2-estágios + reciclo, cascata em série |
| **Comparação de métodos** | ✅ CLI + GUI | `biogassim compare` / aba *Comparação de Métodos*: mesmo backend (`ComparisonEngine`), tabela, ranking, energia/economia, export |

## Validação

Comparações contra literatura (ver `tests/test_validation.py`):

- Solubilidade de CO₂ em água a 25 °C (0,034 mol/(L·atm)) e fatores de
  compressibilidade (Z) via Peng-Robinson.
- Equilíbrio MEA vs. Aronu (2011) e MDEA vs. Huttenhuis et al. (2007).
- Solventes físicos (Selexol/Rectisol) vs. dados de solubilidade
  (Henni 2005, Décultot 2019, Leu & Robinson 1992).
- Fechamento de balanço de massa do flash e do absorvedor (~1e-9 ou melhor).

Validação sistemática contra Aspen Plus/DWSIM é meta futura (ROADMAP).

## Desenvolvimento

```bash
pip install -e ".[dev,excel,gui]"   # pytest, pytest-cov, ruff, openpyxl, PySide6
pytest -q                       # roda os 243 testes (GUI é pulada sem Qt instalado)
pytest --cov=biogassim          # com cobertura
ruff check biogassim tests      # lint
ruff check --fix biogassim tests   # corrige o que for auto-corrigível
```

A integração contínua (GitHub Actions, `.github/workflows/ci.yml`) roda lint e testes
em Python 3.10, 3.11 e 3.12 a cada push e pull request.

## Licença

MIT — ver [`LICENSE`](LICENSE).
