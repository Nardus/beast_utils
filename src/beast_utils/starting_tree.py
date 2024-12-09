# Functions for replacing the starting tree specification in a BEAST xml file

from lxml import objectify

# The tags of the <treeModel> block that specify the starting tree
TREE_TYPES = ["tree", "coalescentTree", "upgmaTree"]


def _get_rescaled_tree(xml_root, id="startingTree"):
    """
    Retreive the <rescaledTree> element from a BEAST xml. If none exists,
    it will be created.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    id : str, optional
        The id of the <rescaledTree> block to find (default: "startingTree").
    
    Returns
    -------
    xml.etree.ElementTree.Element
        The xml element for the tree block.
    """
    tree = xml_root.find(f"rescaledTree[@id='{id}']")
    
    if tree is not None:
        return tree
                
    # No <rescaledTree> block found, create one
    tree = xml_root.makeelement("rescaledTree", {"id": id})
    
    # Find the most appropriate place to insert the tree block
    taxa = xml_root.find("taxa")
    alignments = xml_root.findall("alignment")
    constantSize = xml_root.find("constantSize")
    
    if constantSize is not None:
        # Insert below the <constantSize> block (specifies the initial coalescent model)
        constantSize.addnext(tree)
    elif len(alignments) > 0:
        # Insert below the last existing alignment block
        alignments[-1].addnext(tree)
    elif taxa is not None:
        # Insert below the <taxa> block
        taxa.addnext(tree)
    else:
        # None of these elements exist (yet), so insert as the first element
        xml_root.insert(0, tree)
    
    return tree
    

def _get_tree_model(xml_root, id="treeModel"):
    """
    Retrieve the <treeModel> element of a BEAST xml, raising an informative error message if it
    is missing.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
        
    Returns
    -------
    xml.etree.ElementTree.Element
        The xml element for the tree model block.
    """
    tree_model = xml_root.find(f"treeModel[@id='{id}']")
    
    if tree_model is None:
        raise ValueError(f"No <treeModel> element with id '{id}' found.")
        
    return tree_model


def _get_alignment_id(xml_root):
    """
    Retrieve the id of the first alignment block in the xml file.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
        
    Returns
    -------
    str
        The id of the first alignment block.
    """
    alignment = xml_root.find("alignment")
    
    if alignment is None:
        raise ValueError("No <alignment> block found.")
    
    return alignment.get("id")


def _remove_tree_specification(xml_root, tree_spec, tree_model):
    """
    Remove any existing starting tree specification from a BEAST xml file.
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    tree_spec : xml.etree.ElementTree.Element
        The <rescaledTree> element to remove the specification from.
    tree_model : xml.etree.ElementTree.Element
        The <treeModel> element to remove the specification from.
    
    Returns
    -------
    None
    """
    # Remove any existing starting tree specification
    for child in tree_spec.iterchildren():
        tree_spec.remove(child)

    for child in tree_model.iterchildren():
        if child.tag in TREE_TYPES:
            if child.get("idref") == tree_spec.get("id"):
                tree_model.remove(child)

    # Remove random starting tree if present (these use a different outer tag from tree_spec)
    tree_id = tree_spec.get("id")
    random_tree = xml_root.find(f"coalescentSimulator[@id='{tree_id}']")

    if random_tree is not None:
        xml_root.remove(random_tree)


# Use a UPGMA tree as the starting tree
def use_upgma(xml_root):
    """
    Update a BEAST xml file to use a UPGMA tree as the starting tree. This tree will be based
    on the first alignment in the xml.
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    
    Returns
    -------
    None
    """
    # Get relevant elements
    tree_spec = _get_rescaled_tree(xml_root)
    tree_model = _get_tree_model(xml_root)
    alignment_id = _get_alignment_id(xml_root)
    
    # Remove any existing starting tree specification
    _remove_tree_specification(xml_root, tree_spec, tree_model)
    
    # Add a new UPGMA tree specification
    upgma = objectify.SubElement(tree_spec, "upgmaTree")
    distmat = objectify.SubElement(upgma, "distanceMatrix", {"correction": "JC"})
    patterns = objectify.SubElement(distmat, "patterns")
    objectify.SubElement(patterns, "alignment", {"idref": alignment_id})
    
    # Update <treeModel> block
    tree_ref = tree_model.makeelement("upgmaTree", {"idref": tree_spec.get("id")})
    tree_model.insert(0, tree_ref)


def use_tree(xml_root, newick_tree):
    """
    Update a BEAST xml file to use an existing phylogeny as the starting tree. Note that no
    validity checks are performed on the supplied newick string.
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    newick_tree : str
        The newick tree string.
        
    Returns
    -------
    None
    """
    # Get relevant elements
    tree_spec = _get_rescaled_tree(xml_root)
    tree_model = _get_tree_model(xml_root)
    
    # Remove any existing starting tree specification
    _remove_tree_specification(xml_root, tree_spec, tree_model)
    
    # Add a new tree specification
    newick = objectify.SubElement(tree_spec, "newick", {"usingDates": "true"})
    newick._setText(newick_tree.strip())
    
    # Update <treeModel> block
    tree_ref = tree_model.makeelement("tree", {"idref": tree_spec.get("id")})
    tree_model.insert(0, tree_ref)
