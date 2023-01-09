# Enable logging of Markov jumps and rewards in a BEAST XML file.

import numpy as np

from lxml import objectify


# General
def _get_markov_jump_block(xml_root, attribute_name):
    """
    Get the <markovJumpsTreeLikelihood> block associated with an attribute from a BEAST xml.
    
    An error will be raised if no such block exists.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root element of the BEAST XML.
    attribute_name : str
        Name of a discrete attribute.
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
        Markov jump likelihood block
    """
    likelihood_id = f"{attribute_name}.treeLikelihood"
    likelihood = xml_root.find(f"markovJumpsTreeLikelihood[@id='{likelihood_id}']")

    if likelihood is None:
        raise ValueError(f"No markovJumpsTreeLikelihood block with ID {likelihood_id} found.")
        
    return likelihood


# Jump counts
def _get_jump_count_param(xml_root, attribute_name):
    """
    Get a Markov jump count parameter element from a BEAST xml. If it does not exist, a new 
    parameter element will be created.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root element of the BEAST XML.
    attribute_name : str
        Name of a discrete attribute.
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
        Markov jump count parameter element (may be out of date or uninitialized)
    """
    # Find the relevant <markovJumpsTreeLikelihood> block
    likelihood = _get_markov_jump_block(xml_root, attribute_name)
        
    # Find or create parameter
    param_id = f"{attribute_name}.count"
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
        Markov jump count parameter element.
    n_states : int
        Number of states observed for the attribute counted by this parameter.
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
        Root element of the BEAST XML.
    attribute_name : str
        Name of a discrete attribute.
        
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


# Rewards
def _get_rewards_block(xml_root, attribute_name):
    """
    Get a Markov rewards block from a BEAST xml. If it does not exist, a new (empty) element 
    will be created.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root element of the BEAST XML.
    attribute_name : str
        Name of a discrete attribute.
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
        Markov rewards block (may be empty or out of date)
    """
    # Find the relevant <markovJumpsTreeLikelihood> block
    likelihood = _get_markov_jump_block(xml_root, attribute_name)
    
    # Find or create rewards block
    rewards = likelihood.find("rewards")
    
    if rewards is None:
        rewards = objectify.SubElement(likelihood, "rewards")
    
    return rewards


def _get_reward_param(rewards_block, state_name):
    """
    Get the Markov reward parameter for a specific state, creating one if needed.
    
    Note, the associated rewards parameter should follow the pattern "{state_name}.reward". If no
    parameter with this identifier exists, a new one will be created (but not initialized).
    
    Parameters
    ----------
    rewards_block : lxml.objectify.ObjectifiedElement
        Markov rewards block.
    state_name : str
        Name of the observed state to update.
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
        Markov reward parameter element.
    """
    param_id = f"{state_name}.reward"
    param = rewards_block.find(f"parameter[@id='{param_id}']")
    
    if param is None:
        param = objectify.SubElement(rewards_block, "parameter", {"id": param_id})
        
    return param


def _update_reward_param(reward_param, state_name, observed_states):
    """
    Update a Markov reward parameter to reflect the current order of states in an XML.
    
    Parameters
    ----------
    rewards_block : lxml.objectify.ObjectifiedElement
        Markov rewards block.
    state_name : str
        Name of the observed state to update. 
    observed_states : list of str
        List of all observed states for the attribute associated with the rewards block, in the
        order with which they appear in the XML.
        
    Returns
    -------
    None
    """
    # Build indicator vector
    inds = np.zeros(len(observed_states), dtype=float)
    inds[observed_states.index(state_name)] = 1.0
    
    # String representation (no leading space here)
    inds = inds.astype(str).tolist()
    inds = " ".join(inds)
    
    # Set value
    reward_param.set("value", inds)


def add_markov_reward_log(xml_root, attribute_name):
    """
    Add (or update) parameters to track the Markov rewards for all observed states of a discrete
    attribute. The identifiers of any existing reward parameters should follow the pattern 
    "{observed_state}.reward".
    
    Note that the XML should already contain a <markovJumpsTreeLikelihood> block, achieved by
    e.g. clicking the "Reconstruct states at all ancestors" option in BEAUTI.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root element of the BEAST XML.
    attribute_name : str
        Name of a discrete attribute.
        
    Returns
    -------
    None
    """
    # Get observed states
    datatype_name = f"{attribute_name}.dataType"
    datatype = xml_root.find(f"generalDataType[@id='{datatype_name}']")
    
    if datatype is None:
        raise ValueError(f"No generalDataType element for attribute {attribute_name} found.")
    
    observed_states = [s.get("code") for s in datatype.find("state")]
    
    # Get rewards block
    rewards = _get_rewards_block(xml_root, attribute_name)
    
    # Add/update parameters
    for state in observed_states:
        param = _get_reward_param(rewards, state)
        _update_reward_param(param, state, observed_states)
