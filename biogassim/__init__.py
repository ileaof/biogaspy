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

Status desta entrega: Water Scrubbing e MEA totalmente funcionais (testados);
DEA/MDEA/Selexol/Rectisol/PSA/Membranas como modelos simplificados/stubs
extensíveis. Ver ``docs/ROADMAP.md``.
"""
from .version import __version__

__all__ = ["__version__"]