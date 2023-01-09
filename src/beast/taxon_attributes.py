# Add or replace taxon attributes in a BEAST xml file

import numpy as np

from warnings import warn
from lxml import objectify

from .markov_jump import _update_jump_count_param


def _add_data_type(xml_root, attribute_name):
    """
    Add a <generalDataType> block to a BEAST xml file.
    
    This function also adds an <attributePatterns> block, pointing to the new <generalDataType>. 
    
    Note that xml_root is modified in place, but the <generalDataType> block will be returned
    to allow for further modification.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    attribute_name : str
        Name of the attribute (e.g. "location").
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
    """
    # Find the last patterns block, so we can add the datatype block immediately after it
    last_patterns = xml_root.findall("patterns")[-1]
    insert_index = xml_root.getchildren().index(last_patterns) + 1
    
    # Add the <generalDataType> block
    datatype_id = f"{attribute_name}.dataType"
    datatype = xml_root.makeelement("generalDataType", {"id": datatype_id})
    
    xml_root.insert(insert_index, datatype)
    
    # If the datatype block doesn't exist, the related <attributePatterns> won't exist either
    attribute_patterns = xml_root.makeelement(
        "attributePatterns",
        {"id": f"{attribute_name}.pattern", "attribute": attribute_name}
    )
        
    objectify.SubElement(attribute_patterns, "taxa", {"idref": "taxa"})
    objectify.SubElement(attribute_patterns, "generalDataType", {"idref": datatype_id})
        
    xml_root.insert(insert_index + 1, attribute_patterns)
    
    return datatype


def _update_data_type(xml_root, attribute_name):
    """
    Update a <generalDataType> block in a BEAST xml file. If no <generalDataType> block exists
    for this attribute, it will be added. 
    
    This function will completely replace all <state> blocks in the <generalDataType> block to
    reflect unique attribute values currently present in the XML. This means that any XML elements
    which rely on the order of states in the <generalDataType> will be out of date.
    
    Note that finding all observed values requires iterating over all taxa, so this function 
    should be used sparingly (e.g., after all states have been added to the XML)
    
    Note that `xml_root` is modified in place, but the <generalDataType> block will be returned
    to allow for further modification.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    attribute_name : str
        Name of the attribute (e.g. "location").
    
    Returns
    -------
    lxml.objectify.ObjectifiedElement
    """
    # Collect all observed states (order does not matter)
    attribute_values = set()
    
    for taxon in xml_root.taxa.iterchildren("taxon"):
        attr = taxon.find(f"attr[@name='{attribute_name}']")
        
        attribute_values.add(attr.text.strip())
    
    attribute_values = sorted(attribute_values)
    
    # Find or create the relevant <generalDataType> block
    datatype_id = f"{attribute_name}.dataType"
    datatype = xml_root.find(f"generalDataType[@id='{datatype_id}']")
    
    if datatype is None:
        datatype = _add_data_type(xml_root, attribute_name)
    
    # Replace all <state> blocks
    for state in datatype.iterchildren("state"):
        datatype.remove(state)
        
    for value in attribute_values:
        objectify.SubElement(datatype, "state", {"code": value})
        
    return datatype


def _update_markov_jumps_tree_likelihood(xml_root, attribute_name, n_states):
    """
    Update the <markovJumpsTreeLikelihood> block in a BEAST xml file (if present). This function
    will update the "{attribute_name}.count" parameter to reflect the order of states in an XML, 
    but cannot update parameters pointing to transitions between specific states - XMLs should log 
    the complete jump history instead. 
    
    `xml_root` is modified in place.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    attribute_name : str
        Name of an attribute (e.g. "location").
    n_states : int
        Number of unique states observed for this attribute.
    
    Returns
    -------
    None
    """
    # Expected names
    likelihood_id = f"{attribute_name}.treeLikelihood"
    param_id = f"{attribute_name}.count"
    
    # Find the relevant <markovJumpsTreeLikelihood> block
    likelihood = xml_root.find(f"markovJumpsTreeLikelihood[@id='{likelihood_id}']")
    
    if likelihood is None:
        warn(f"No markovJumpsTreeLikelihood block with ID {likelihood_id} found. Skipping update.",
             stacklevel=3, category=RuntimeWarning)
        return
    
    # Check available parameters
    params = {p.get("id"): p for p in likelihood.iterchildren("parameter")}
    
    if (param_id in params and len(params) > 1) or (param_id not in params and len(params) > 0):
        warn(f"markovJumpsTreeLikelihood contains parameters which cannot be updated to reflect "
             "newly-added attribute state(s).", stacklevel=3, category=RuntimeWarning)
    
    if param_id not in params:
        warn(f"markovJumpsTreeLikelihood with id {likelihood_id} has no '{param_id}' parameter. "
             "Skipping update.", stacklevel=3, category=RuntimeWarning)
        return
    
    # Update overall jump count parameter to match current number of states
    _update_jump_count_param(params[param_id], attribute_name, n_states)


def add_taxon_attribute(xml_root, taxon_id, attribute_name, attribute_value, 
                        update_other_blocks=True):
    """
    Add or replace a taxon attribute block for a single taxon in a BEAST XML.
    
    Adding an attribute involves updating both the <taxa> and <generalDataType> sections of the 
    xml. If the attribute already exists for a given taxon, it is replaced. Note that this function 
    adds an <attribute> block (i.e., a block describing data for a taxon), and not an actual XML 
    attribute (as in <taxon atrribute_name=attribute_value>).
    
    xml_root is modified in place.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    taxon_id : str
        Taxon for which the attribute should be added or replaced.
    attribute_name : str
        Name of the attribute (e.g. "location").
    attribute_value : str
        Value to add for this attribute.
    update_other_blocks : bool
        Should the <generalDataType> and <markovJumpsTreeLikelihood> blocks be updated to reflect 
        new states? (default: True)
    """
    # Find taxon
    taxon = xml_root.taxa.find(f"taxon[@id='{taxon_id}']")
    
    if taxon is None:
        raise ValueError(f"Taxon '{taxon_id}' not found in <taxa> block.")
    
    # Add (or update) the attribute
    attribute = taxon.find(f"attr[@name='{attribute_name}']")
    
    if attribute is None:
        attribute = objectify.SubElement(taxon, "attr", {"name": attribute_name})
    
    attribute._setText(attribute_value)
    
    # Perform other updates if requested (useful as a safety mechananism when adding a 
    # single attribute by calling this function directly)
    if update_other_blocks:
        datatype = _update_data_type(xml_root, attribute_name)
        
        n_states = len(datatype.findall("state"))
        _update_markov_jumps_tree_likelihood(xml_root, attribute_name, n_states)


def add_taxon_attributes(xml_path, output_path, attribute_name, attribute_dict):
    """
    Add or replace taxon attributes for multiple taxa in a BEAST XML file.
    
    See `add_taxon_attribute` for more details.
    
    Parameters
    ----------
    xml_path : str
        Path to a BEAST xml file.
    output_path : str
        Path to use for the output xml file.
    attribute_name : str
        Name of the attribute (e.g. "location").
    attribute_dict : dict
        Dictionary mapping taxon IDs to attribute values.
    """
    tree = objectify.parse(xml_path)
    root = tree.getroot()
    
    for taxon_id, attribute_value in attribute_dict.items():
        add_taxon_attribute(root, taxon_id, attribute_name, attribute_value, 
                            update_other_blocks=False)
        
    # Update other elements to reflect final states
    datatype = _update_data_type(root, attribute_name)

    n_states = len(datatype.findall("state"))
    _update_markov_jumps_tree_likelihood(root, attribute_name, n_states)
    
    # Save to file
    with open(output_path, "wb") as f:
        tree.write(
            f,
            pretty_print=True,
            encoding="utf-8",
            doctype='<?xml version="1.0" standalone="yes"?>'
        )
