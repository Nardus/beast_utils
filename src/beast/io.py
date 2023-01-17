# Input / output functions

from lxml import objectify
from lxml.etree import ElementTree

def from_string(string):
    """
    Parse an xml string.
    
    Parameters
    ----------
    string : str
        The xml string.
    
    Returns
    -------
    lxml.etree.ElementTree
        The xml tree.
    """
    parser = objectify.makeparser(remove_blank_text=True)
    root = objectify.fromstring(string, parser=parser)
    return ElementTree(root)


def read_xml(xml_path):
    """
    Read a BEAST XML file.
    
    Parameters
    ----------
    xml_path : str
        Path to the xml file.
    
    Returns
    -------
    lxml.etree.ElementTree
        The xml tree.
    """
    parser = objectify.makeparser(remove_blank_text=True)
    return objectify.parse(xml_path, parser=parser)


def write_xml(tree, output_path):
    """
    Write a BEAST XML to disk, ensuring the doctype string is set appropriately.
    
    Parameters
    ----------
    tree : lxml.etree.ElementTree
        The xml tree to write.
    output_path : str
        Path to write the xml to.
    
    Returns
    -------
    None
    """
    with open(output_path, "wb") as f:
        tree.write(
            f,
            pretty_print=True,
            encoding="utf-8",
            doctype='<?xml version="1.0" standalone="yes"?>'
        )
