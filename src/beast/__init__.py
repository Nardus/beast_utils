# Functions for updating or modifying BEAST xml files

# Expose commonly-used functions directly:
from .update_from_template import update_from_template

from .add_taxon import add_taxon, add_unsampled_taxon
from .add_taxon_attributes import add_taxon_attributes
from .predictor import add_predictor

from .set_run_length import set_run_length
