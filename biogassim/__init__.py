"""BioGasSim -- simulador científico de upgrading de biogás.

Pacotes:
  Core            -- constantes, unidades, solver numérico, convergência
  Thermodynamics  -- EOS cúbicas (PR, SRK), Lei de Henry, fugacidade, flash
  Properties      -- banco de componentes puros e misturas
  MassTransfer    -- difusão, teoria dos dois filmes, correlações
  Hydraulics      -- recheios, flooding, perda de carga
  UnitOperations  -- correntes, absorvedor, stripper, compressor, trocadores
  Solvents        -- água (físico), MEA/DEA/MDEA (químico), Selexol, Rectisol
  PSA             -- isoteras, ciclo PSA
  Membranes       -- permeabilidades, modelo solução-difusão
  Optimization    -- energia, economia, sensibilidade
  Export          -- CSV/JSON/Excel/HTML (+ stubs PDF/Tecplot/VTK)
  Reporting       -- gráficos (matplotlib)

Status (v0.2): Water Scrubbing e MEA validados ponta-a-ponta; DEA/MDEA com
especiação Kent-Eisenberg rigorosa (MDEA calibrado vs. VLE); Selexol/Rectisol
(solventes físicos) calibrados vs. literatura; PSA e Membranas como modelos
simplificados/extensíveis. Ver ``docs/ROADMAP.md`` e ``CHANGELOG.md``.
"""
from . import safety
from .version import __version__

__all__ = ["__version__", "safety"]
