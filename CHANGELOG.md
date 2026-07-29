# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
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
