# Update an XML file based on a template XML

from warnings import warn

from lxml import objectify
from lxml.etree import _ElementTree, tostring

def _prepare_template(root, template):
    """
    Prepare a template XML for use in `update_from_template` or `remove_with_template`, and 
    check validity.
    
    Parameters
    ----------
    root : lxml.etree._ElementTree
        root element of the XML to be updated.
    template : str or lxml.etree._ElementTree
        Either an existing lxml object or a path to the template XML file.
    
    Returns
    -------
    lxml.etree._ElementTree
        root element of the template XML.
    """
    if isinstance(template, str):
        parser = objectify.makeparser(remove_blank_text=True, remove_comments=True)
        template_tree = objectify.parse(template, parser=parser)
        template_root = template_tree.getroot()
    else:
        template_root = template.getroot()
    
    # Check outer tags
    if root.tag != "beast":
        raise ValueError("XML must contain an outer <beast> tag.")
    
    if template_root.tag != "beast":
        raise ValueError("Template must contain an outer <beast> tag.")
    
    if root.get("version") != template_root.get("version"):
        raise ValueError("BEAST versions do not match.")
        
    return template_root


def _removal_error(template):
    """
    Raise an error indicating that an element to be removed does not exist.
    
    Parameters
    ----------
    template : lxml.objectify.ObjectifiedElement
        Template element.
    
    Returns
    -------
    None
    """
    # Get string representation of the opening tag of the template element
    string_representation = tostring(template, pretty_print=True).decode("utf-8")
    string_representation = string_representation.split("\n")[0]
    
    # Raise error
    message = "Element to be removed either does not exist or does not contain the child " +\
              f"elements specified in the removal template: {string_representation}."

    raise ValueError(message)


def _find_candidate_matches(parent, template):
    """
    Find candidate matches for a template element in a parent XML. Elements are matched
    based on their tag and if present, also their id, idref, or name attributes, in that order.
    
    Parameters
    ----------
    parent : lxml.objectify.ObjectifiedElement
        Parent element.
    template : lxml.objectify.ObjectifiedElement
        Template element.
    
    Returns
    -------
    list
        List of candidate matches.
    """
    if template.get("id") is not None:
        search_string = f"""{template.tag}[@id="{template.get('id')}"]"""
    elif template.get("idref") is not None:
        search_string = f"""{template.tag}[@idref="{template.get('idref')}"]"""
    elif template.get("name") is not None:
        search_string = f"""{template.tag}[@name="{template.get('name')}"]"""
    else:
        search_string = template.tag

    return parent.findall(search_string)


def _match_subtrees(parent, template, top_level=True):
    """
    Check if a parent XML contains a subtree matching a template XML. Elements are matched
    based on their tag and if present, also their id, idref, or name attributes, in that order. 
    If the template element has children, these are checked recursively. Note that this function
    will return True if the parent contains a subtree matching the template, even if the parent
    contains additional elements not present in the template.
    
    Parameters
    ----------
    parent : lxml.objectify.ObjectifiedElement
        Parent element.
    template : lxml.objectify.ObjectifiedElement
        Template element.
    top_level : bool
        Whether this function was called directly or recursively. If True, the parent element
        is assumed to match, and only its children are checked.
    
    Returns
    -------
    bool
        True if the parent contains a subtree matching the template, False otherwise.
    """
    # If there are no more children, we have a potential match
    if len(template.getchildren()) == 0:
        if template.tag != parent.tag:
            return False
        
        template_id = template.get("id") or template.get("idref") or template.get("name")
        parent_id = parent.get("id") or parent.get("idref") or parent.get("name")
        
        if template_id is None:
            # Nothing else to match on, so assume a match
            return True
        
        return template_id == parent_id
    
    # Find match candidates
    if top_level:
        candidates = [parent]
    else:
        candidates = _find_candidate_matches(parent, template)
    
    # Check immediate children of all candidates
    for cand in candidates:
        for child in template.getchildren():
            if child.tag == "comment":
                # Ignore comments
                continue
            
            if not _match_subtrees(cand, child, top_level=False):
                return False
        
        return True


def add_element(parent, template, position=None):
    """
    Add an element to a parent XML. The template element can be nested, in which case all
    children not identifiable in the parent will be added recursively at the appropriate
    level. When adding elements below existing parents, both the tag name and id attribute 
    must match (tags with no id attribute will always result in creation of a new element).
    Note that when multiple elements with the same tag and id exist, only the first will be
    updated.
    
    Operations are performed in place, modifying the parent.
    
    Parameters
    ----------
    parent : lxml.objectify.ObjectifiedElement
        Parent element.
    template : lxml.objectify.ObjectifiedElement
        Template element.
    position : int
        Position at which to insert the template. Note that this determines the order,
        not the level within the hierarchy. If None (the default), new elements are
        appended after any existing elements belonging to a given parent.
        
    Returns
    -------
    None
    """    
    # Check if element already exists
    existing_element = None

    if template.get("id") is not None:
        for child in parent.getchildren():
            if child.tag == template.tag and child.get("id") == template.get("id"):
                existing_element = child
                break

    # Add element (if needed)
    if existing_element is None:
        existing_element = parent.makeelement(template.tag, template.attrib)

        if position is not None:
            parent.insert(position, existing_element)
        else:
            parent.append(existing_element)

    # Add children
    for child in template.getchildren():
        add_element(existing_element, child)


def remove_element(parent, template):
    """
    Remove an element from a parent XML. The template element can be nested, in which case all
    parent elements left empty by removal of the inner-most element will also be removed. When
    removing elements below existing parents, both the tag name and id attribute of the parent
    must match. If the id attribute is not present or a given tag/id combination matches multiple
    elements, only the first match will be removed. Removing elements with children is only 
    supported if the removal template also matches (and hence removes) all children. Elements
    in the removal template that cannot be matched in the parent will be ignored.
    
    Operations are performed in place, modifying the parent.
    
    Parameters
    ----------
    parent : lxml.objectify.ObjectifiedElement
        Parent element.
    template : lxml.objectify.ObjectifiedElement
        Template element.
    
    Returns
    -------
    None
    """
    # Find candidate matches
    candidates = _find_candidate_matches(parent, template)
    
    if len(candidates) == 0:
        _removal_error(template)
    
    # If there are no children, just remove the first match
    if len(template.getchildren()) == 0:
        if len(candidates) > 1:
            identifier = template.get("id") or template.get("idref") or template.get("name")
            warn(f"Multiple matches found for {template.tag} with id/idref/name {identifier}. " +
                 "Only the first will be removed.")
        parent.remove(candidates[0])
        return
    
    # Try find a match that has the correct children (though it may also have additional children)
    removal_parent = None
    
    for cand in candidates:
        if _match_subtrees(cand, template):
            removal_parent = cand
            break
        
    if removal_parent is None:
        _removal_error(template)
    
    # Remove any children that are also in the removal template
    removal_children = [c for c in template.getchildren() if c.tag != "comment"]
    original_children = [c for c in removal_parent.getchildren() if c.tag != "comment"]
    
    for child in removal_children:
        remove_element(removal_parent, child)
        
    # If all children have been removed, remove the parent too
    if len(original_children) == len(removal_children):
        parent.remove(removal_parent)


def update_from_template(tree, template, before_operators=True):
    """
    Update an XML tree based on a template XML. The template XML should match the structure 
    of the XML to be updated, which determines where new elements are added. Note that existing 
    elements will not be changed. 
    
    To allow identification of existing parent elements, only the tag name and id attribute are 
    needed (e.g. `<operators id="operators">`). If the id attribute is not present, a new element 
    will be created even if the tag already exists. The outer `<beast>` tag should include the
    version attribute (e.g. `<beast version="1.10.4">`), and this must match between the template
    and the XML to be updated.
    
    Note on element order: in most cases, new elements will always be added after any existing 
    elements below a given parent tag. The only exception is when adding elements to the top-level
    `<beast>` tag, in which any new elements before or after the <operators> element will retain 
    this position. If the template contains no <operators> tag, use the `before_operators` 
    argument to specify where new top-level elements should be added.
    
    `tree` is modified in place.

    Parameters
    ----------
    tree : lxml.etree.ElementTree
        XML tree to be updated.
    template : lxml.etree.ElementTree or str
        Either an existing lxml object or a path to the template XML file.
    before_operators : bool, optional
        If True, new top-level elements will be added before the <operators> element. If False, 
        they will be added after the <operators> element. This argument is ignored if the template 
        itself contains an <operators> element (default: True).

    Returns
    -------
    lxml.etree.ElementTree
        The updated XML tree.
    """
    if not isinstance(tree, _ElementTree):
        raise ValueError("tree is not an lxml.etree._ElementTree object.")

    root = tree.getroot()

    # Read template
    template_root = _prepare_template(root, template)
    
    # Update XML
    template_children = template_root.getchildren()
    template_contains_operators = template_root.find("operators") is not None

    if before_operators or template_contains_operators:
        # Find the <operators> tag in the master xml
        for position, child in enumerate(root.iterchildren()):
            if child.tag == "operators":
                break

        # Add elements before <operators> tag
        for i, child in enumerate(template_children):
            if child.tag == "operators":
                break
            else:
                add_element(root, child, position=position)
                position += 1

    # Add any remaining children (continuing from i, which might be template_xml's operators block)
    for child in template_children[i:]:
        add_element(root, child)

    return tree


def remove_with_template(tree, template):
    """
    Remove elements from an XML tree based on a template XML. The template XML should match the
    structure of the XML to be updated, which determines which elements are removed.
    
    To allow identification of existing parent elements, only the tag name and id attribute are
    needed (e.g. `<operators id="operators">`). If the id attribute is not present, all elements
    with the given tag will be removed. If element contains no children after removing the
    specified elements, it will also be removed. The outer `<beast>` tag should include the
    version attribute (e.g. `<beast version="1.10.4">`), and this must match between the template
    and the XML to be updated.
    
    `tree` is modified in place.
    
    Parameters
    ----------
    tree : lxml.etree.ElementTree
        XML tree to be updated.
    template : lxml.etree.ElementTree or str
        Either an existing lxml object or a path to the template XML file.
    
    Returns
    -------
    lxml.etree.ElementTree
        The updated XML tree.
    """
    if not isinstance(tree, _ElementTree):
        raise ValueError("tree is not an lxml.etree._ElementTree object.")

    root = tree.getroot()

    # Read template
    template_root = _prepare_template(root, template)
    
    # Remove elements
    for child in template_root.getchildren():
        remove_element(root, child)
    
    return tree
