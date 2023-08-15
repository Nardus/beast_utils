# Update an XML file based on a template XML

from warnings import warn

from lxml import objectify
from lxml.etree import _ElementTree


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


def update_from_template(tree, template, before_operators=True):
    """
    Update an XML tree based on a template XML. The template XML should match the structure 
    of the XML to be updated, which determines where new elements are added. Note that existing 
    elements will cannot be changed. 
    
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
    if isinstance(template, str):
        parser = objectify.makeparser(remove_blank_text=True, remove_comments=True)
        template_tree = objectify.parse(template, parser=parser)
        template_root = template_tree.getroot()
    else:
        template_tree = template
        template_root = template_tree.getroot()
    
    # Check outer tags
    if root.tag != "beast":
        raise ValueError("XML must contain an outer <beast> tag.")
    
    if template_root.tag != "beast":
        raise ValueError("Template must contain an outer <beast> tag.")
    
    if root.get("version") != template_root.get("version"):
        raise ValueError("BEAST versions do not match.")
    
    # Update XML
    template_children = template_root.getchildren()
    template_contains_operators = template_root.find("operators") is not None
    
    if before_operators or template_contains_operators:
        # Find the <operators> tag in the master xml
        for position, child in enumerate(root.iterchildren()):
            if child.tag == "operators":
                break
        
        # Add elements before <operators> tag
        for i in range(0, len(template_children)):
            child = template_children[i]
            
            if child.tag == "operators":
                break
            else:
                add_element(root, child, position=position)
                position += 1
    
    # Add any remaining children (continuing from i, which might be template_xml's operators block)
    for j in range(i, len(template_children)):
        child = template_children[j]
        
        add_element(root, child)
    
    return tree
