# Functions for updating or modifying BEAST xml files

# Expose submodules:
from . import io
from . import utils
from . import substitution_model
from . import starting_tree

# Expose commonly-used functions directly:
from .io import read_xml, write_xml
from .templating import update_from_template, remove_with_template

from .taxon import add_taxon, add_unsampled_taxon
from .taxon_attributes import add_taxon_attributes
from .predictor import add_predictor
from .markov_jump import add_markov_jump_count_log, add_markov_reward_log
