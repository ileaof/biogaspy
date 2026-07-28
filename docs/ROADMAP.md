# Roadmap do BioGasSim

Esta entrega (v0.1) estabelece a fundação arquitetada e dois processos totalmente
funcionais (Water Scrubbing, MEA). Os itens abaixo levam o simulador à paridade com
a especificação completa (nível Aspen/DWSIM).

## Curto prazo (robustez e fidelidade)

- [x] **Newton global no Absorvedor**: Newton-Raphson sobre o resíduo MESH
      consistente (variáveis = fluxos das espécies voláteis; V_j pelo balanço
      total, eliminando singularidade) via `Core.solver.newton_raphson`, com
      aquecimento por substituição sucessiva. Converge em toda a faixa de L/V
      incluindo o pinch que antes divergia (MEA L/V=8..15); balanço fecha em
      ~1e-12. `method="newton"` (padrão) ou `"ss"`.
- [x] **Modelo de amina rigoroso (Kent-Eisenberg)**: especiação CO₂-MEA-H₂O
      (carbamato/bicarbonato/carbonato) em `Solvents/KentEisenberg.py`,
      integrado ao `MEASolvent` (`method="kent-eisenberg"`, padrão). β₁/β₂
      calibrados contra Jou-Mather-Otto (1995) / Aronu et al. (2011), 30% máss.
      MEA a 40 °C: p_CO2(α) dentro de fator ~4 (modelo aparente, sem coef. de
      atividade). O K efetivo calibrado permanece como `method="effective"`.
- [x] **Balanço de energia por estágio (modo adiabático)**: laço externo
      MESH<->energia -- Newton global (MESH a T fixo) alternado com o balanço de
      entalpia por estágio (sistema tridiagonal em T, calor de absorção como
      fonte exotérmica, fronteiras T_lean/T_gas). Produz a "temperature bulge"
      na ponta rica (MEA: 40 -> ~61 °C) e elevação de T fisicamente coerente;
      balanço de massa e energia validados em `tests/test_validation.py`.
- [x] **Validação contra literatura**: `tests/test_validation.py` (Z PR de
      CH₄/CO₂, HCP de Henry CO₂/água, equilíbrio MEA vs Aronu, balanço do
      absorvedor) + `tests/validation_table.py` gera tabela de desvios em
      CSV/JSON (`examples_output/validation.*`).
- [x] **Estudo de sensibilidade paramétrica**: `Optimization/Sensitivity.py`
      com `sweep()` (1-D) e `sweep_grid()` (2-D, heatmap) sobre pressão, T_op,
      N_stages, altura e L/V, reusando o Newton global (robusto em toda a faixa
      -- antes a SS divergia perto do pinch). Pontos não-convergidos
      (solvente sobrecarregado, rich loading > α_max) reportam NaN nas
      métricas em vez de valores sem sentido físico. Exemplo
      `Examples/Sensitivity.py` exporta CSV/JSON/PNG; testes em
      `tests/test_sensitivity.py` (monotonicidade física, formato da grade,
      carregamento viável).
- [x] **Hidráulica de coluna rigorosa**: correlação de flooding GPDC de Eckert
      (SI) com curva de flood calibrada vs anéis Pall (Pall 50 ~2,2 m/s,
      Pall 25 ~1,4 m/s em ar/água 1 atm), e perda de carga mecânica de
      Stichlmair-Bravo-Fair (1989) -- Ψ0=C1/Re+C2/√Re+C3, holdup
      h_L=0,555·Fr^(1/3), ΔP_molh=ΔP_seco·(ε/(ε-h_L))^4,65. Banco de
      recheios ampliado (13 tipos, com constantes C1/C2/C3 de Stichlmair).
      Corrigidos bugs de unidade em `Diffusion.py` (Wilke-Chang ×1e-4 cm²/s->m²/s,
      Fuller √(1/Ma+1/Mb)). Testes diretos em `tests/test_hydraulics.py` (13) e
      `tests/test_masstransfer.py` (14) -- antes esses pacotes tinham ZERO testes.
- [x] **Especiação Kent-Eisenberg para DEA e MDEA**: modelo generalizado em
      `Solvents/KentEisenberg.py` (chaves de especiação genéricas, β2=0 para
      amina terciária). DEA (amina 2ária, carbamato, pKa~8,9, α_max~0,5) e MDEA
      (amina 3ária, sem carbamato, pKa~8,65, α_max~1,0) agora usam especiação
      rigorosa em vez do stub effective-H. Tendências físicas validadas: pCO2
      monotônico em α, MEA<DEA<MDEA (amina mais fraca -> maior pCO2), pCO2 sobe
      com T, pinch de carbamato em DEA vs curva suave em MDEA. Bug de convenção
      de sinal corrigido em `PhysicalSolvents.py` (van't Hoff: T menor -> mais
      solúvel, consistente com `Thermodynamics.Henry`) -- antes Rectisol a frio
      era LESS eficiente (errado). Testes em `tests/test_solvents.py` (13):
      DEA/MDEA/Selexol/Rectisol antes tinham ZERO testes.
- [x] **Calibração VLE de MDEA contra Huttenhuis (2007)**: regressão
      2-parâmetros (log β1, ΔH1) via Nelder-Mead em escala log sobre dados de
      35 wt% MDEA (m=3,05 mol/L) a 298,15 K e 283,15 K. Resultado: log β1=8,634
      (≈ pKa da MDEA, 8,65 -- fisicamente limpo) e ΔH1=-41,97 kJ/mol
      (protonação exotérmica). p_CO2(α) do modelo concorda com a literatura
      dentro de fator ~2,4 em todo o intervalo, e dentro de fator 1,5 na faixa
      de operação (α 0,10-0,28); T-dependência reproduzida nas duas
      temperaturas. Aplicado em `Solvents/MDEA.py`; validado em
      `tests/test_validation.py` (HUTTENHUIS_MDEA_*K, 4 testes).

## Médio prazo (tecnologias)

- [ ] **PSA dinâmico**: ciclo Skarstrom completo (pressurização, adsorção, blowdown,
      purga), múltiplos leitos, integração temporal, balanço de energia do leito.
- [ ] **Membranas multi-estágio**: reciclo, cascata, modelo cross-flow resolvido
      (não só corte de estágio fixo).
- [~] **Selexol / Rectisol**: seletividade H₂S/CO₂ e regime de baixa T agora
      implementados e testados (`test_solvents.py`); convenção de van't Hoff
      corrigida. Falta: calibrar href absolutos contra dados de solubilidade,
      propriedades físicas (ρ/μ/Cp) por correlação em vez de constantes.
- [ ] **Absorção híbrida**: membrana + amina integrada.

## Interface e exportação

- [ ] **GUI PySide6/PyQt6**: formulários, assistente de casos, visualização em
      tempo real, barras de progresso, comparação lado a lado.
- [ ] **Export PDF** (reportlab), **Tecplot** (.plt), **VTK** (malha estruturada
      da coluna para visualização 3D).
- [ ] **Sphinx**: manual do usuário, do desenvolvedor, API reference.

## Desempenho

- [ ] **Paralelização**: Numba (@jit) nos loops de estágio; CUDA Python/CuPy para
      estudos paramétricos massivos (varredura de P, T, L/G).
- [ ] **Matrizes esparsas** no Jacobiano do Newton global.

## Qualidade

- [x] Cobertura ampliada: transporte e hidráulica agora testados direto
      (`test_masstransfer.py`, `test_hydraulics.py`); sensibilidade
      (`test_sensitivity.py`); DEA/MDEA/Selexol/Rectisol (`test_solvents.py`);
      MDEA vs Huttenhuis (`test_validation.py`). Falta: economia, propriedades
      de transporte (viscosidade/condutividade de mistura), calibração de VLE
      para DEA (dados abertos ainda não encontrados) e href para Selexol/Rectisol.
- [ ] CI (GitHub Actions): lint, pytest em Linux/Windows/macOS.
- [ ] Empacotamento no PyPI.