# Reaper Module — Shadow's Research & Data Collection
# "The one who harvests knowledge from the outside world."
#
# Usage:
#   from modules.grimoire import Grimoire
#   from modules.reaper import Reaper
#
#   grimoire = Grimoire()
#   reaper = Reaper(grimoire)
#   reaper.run_standing_research()  # One command does everything

from .reaper import Reaper, evaluate_source
from .config import STANDING_TOPICS
