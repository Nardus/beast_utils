# Enable logging of Markov jumps and rewards in a BEAST XML file.

import numpy as np

from lxml import objectify

# Jump counts
def _get_jump_count_param(xml_root, attribute_name):
    """
    Get a Markov jump count parameter element from a BEAST xml. If it does not exist, a new 
    parameter element will be created.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root element of the BEAST XML
    attribute_name : str
        Name of a discrete attribute
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
        Markov jump count parameter element (may be out of date or uninitialized)
    """
    # Expected names
    likelihood_id = f"{attribute_name}.treeLikelihood"
    param_id = f"{attribute_name}.count"

    # Find the relevant <markovJumpsTreeLikelihood> block
    likelihood = xml_root.find(f"markovJumpsTreeLikelihood[@id='{likelihood_id}']")

    if likelihood is None:
        raise ValueError(f"No markovJumpsTreeLikelihood block with ID {likelihood_id} found.")
        
    # Find or create parameter
    param = likelihood.find(f"parameter[@id='{param_id}']")
    
    if param is None:
        param = objectify.SubElement(likelihood, "parameter", {"id": param_id})
        
    return param


def _update_jump_count_param(param, n_states):
    """
    Update a Markov jump count parameter ensuring that transitions between all observed states
    are counted
    
    Parameters
    ----------
    param : lxml.objectify.ObjectifiedElement
        Markov jump count parameter element
    n_states : int
        Number of states observed for the attribute counted by this parameter
    """
    # Build matrix
    indicator_vals = np.ones((n_states, n_states), dtype=float)
    np.fill_diagonal(indicator_vals, 0.0)

    # String representation (leading space character is required)
    indicator_vals = indicator_vals.astype(str).flatten().tolist()
    indicator_vals = " " + " ".join(indicator_vals)
    
    # Update
    param.set("value", indicator_vals)


def add_markov_jump_count_log(xml_root, attribute_name):
    """
    Add (or update) a parameter counting the Markov jumps between all possible source-destination
    combinations of a discrete attribute.
    
    Note that the XML should already contain a <markovJumpsTreeLikelihood> block, achieved by
    e.g. clicking the "Reconstruct states at all ancestors" option in BEAUTI. This function is
    equivalent to enabling the "Reconstruct state change counts" option, and ensures that all
    attribute states currently present in the XML are captured.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root element of the BEAST XML
    attribute_name : str
        Name of a discrete attribute
        
    Returns
    -------
    None
    """
    # Count states
    datatype_name = f"{attribute_name}.dataType"
    datatype = xml_root.find(f"generalDataType[@id='{datatype_name}']")
    
    if datatype is None:
        raise ValueError(f"No generalDataType element for attribute {attribute_name} found.")
    
    # dataType block may contain other elements (e.g. comments)
    n_states = len(datatype.find("state"))
    
    # Add/update jump count parameter
    jump_count = _get_jump_count_param(xml_root, attribute_name)
    _update_jump_count_param(jump_count, n_states)
