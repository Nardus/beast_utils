# Add or replace taxon attributes in a BEAST xml file

from lxml import objectify


def add_data_type(xml_root, attribute_name):
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


def add_taxon_attribute(xml_root, taxon_id, attribute_name, attribute_value):
    """
    Add or replace a taxon attribute block in a BEAST xml file.
    
    Adding an attribute involves updating both the <taxa> and <generalDataType> sections of the 
    xml. If the attribute already exists for a given taxon, it is replaced. Note that this function 
    adds a <attribute> block (i.e., a block describing data for a taxon), and not an actual XML 
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
    """
    # Update the <taxa> block
    taxa = xml_root.taxa
    
    for taxon in taxa.iterchildren("taxon"):
        if taxon.get("id") == taxon_id:
            # Update (or add) the attribute
            for attribute in taxon.iterchildren("attr"):
                if attribute.get("name") == attribute_name:
                    attribute._setText(attribute_value)
                    break
            else:
                # Not found, so add it
                attribute = objectify.SubElement(taxon, "attr", {"name": attribute_name})
                attribute._setText(attribute_value)
            
            break
    else:
        raise ValueError(f"Taxon '{taxon_id}' not found in <taxa> block.")
    
    # Find or create the relevant <generalDataType> block
    datatype_id = f"{attribute_name}.dataType"
    
    for datatype in xml_root.iterchildren("generalDataType"):
        if datatype.get("id") == datatype_id:
            break
    else:
        datatype = add_data_type(xml_root, attribute_name)
    
    
    # Add the observed value to the <generalDataType> block (if needed)
    for state in datatype.iterchildren("state"):
        if state.get("code") == attribute_value:
            break
    else:
        objectify.SubElement(datatype, "state", {"code": attribute_value})
        
    # Update <markovJumpsTreeLikelihood> with the correct number of states
    #TODO


def add_taxon_attributes(xml_path, output_path, attribute_name, attribute_dict):
    """
    Add or replace taxon attributes in a BEAST xml file.
    
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
        add_taxon_attribute(root, taxon_id, attribute_name, attribute_value)
    
    with open(output_path, "wb") as f:
        tree.write(
            f,
            pretty_print=True,
            encoding="utf-8",
            doctype='<?xml version="1.0" standalone="yes"?>'
        )
