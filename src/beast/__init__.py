# Functions for updating or modifying BEAST xml files

# Expose commonly-used functions directly:
from .templating import update_from_template

from .taxon import add_taxon, add_unsampled_taxon
from .taxon_attributes import add_taxon_attributes
from .predictor import add_predictor
