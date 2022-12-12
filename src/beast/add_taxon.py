# Add a new taxon and sequence to a BEAST xml file.

from lxml import objectify


def _check_alignment_compatibility(alignment_block, sequence, missing, sequence_type,
                                   alignment_id, taxon_id):
    """
    Check that a sequence is compatible with an existing alignment block.
    
    Parameters
    ----------
    alignment_block : lxml.objectify.ObjectifiedElement
        Alignment block to check.
    sequence : str
        Sequence to check.
    missing : str
        Character(s) which indicate missing data (e.g., "-?").
    sequence_type : str
        Type of sequence (e.g., nucleotide).
    alignment_id : str
        ID of the alignment block (used for informative error messages).
    taxon_id : str
        ID of the taxon for which a sequence is being checked.
    
    Returns
    -------
    None
    """
    message_base = f"does not match existing alignment '{alignment_id}' (taxon: {taxon_id})."
    
    # Check attributes
    if hasattr(alignment_block, "missing"):
        if alignment_block.get("missing") != missing:
            raise ValueError("Missing data character " + message_base)

    if alignment_block.get("dataType") != sequence_type:
        raise ValueError(f"Sequence type '{sequence_type}' " + message_base)
                    
    # Check sequence length (if at least one sequence is already present)
    if hasattr(alignment_block, "sequence"):
        if hasattr(alignment_block.sequence, "taxon"):
            first_sequence = alignment_block.sequence.taxon.tail
            
            if first_sequence is not None:
                first_sequence = first_sequence.strip()
                
                if len(sequence) != len(first_sequence):
                    raise ValueError(f"Sequence length ({len(sequence)}) " + message_base)


def add_taxon_block(xml_root, taxon_id, date, direction="forwards", units="years"):
    """
    Add a new taxon to the <taxa> block of a BEAST xml. The <taxa> block will be created if it
    does not exist yet.
    
    `xml_root` is modified in place.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    taxon_id : str
        Name of a taxon to add.
    date : float
        Sampling date associated with this taxon.
    direction : str, optional
        Direction of time (forwards or backwards).
    units : str, optional
        Units of `time`. By default, this is "years", meaning `date` should be in decimal years.
        
    Returns
    -------
    None
    """
    # Create the <taxa> block if it doesn't exist
    if not hasattr(xml_root, "taxa"):
        taxa = xml_root.makeelement("taxa", {"id": "taxa"})
        xml_root.insert(0, taxa)  # Insert as the first element
    else:
        taxa = xml_root.taxa
    
    # Add the taxon
    taxon = objectify.SubElement(taxa, "taxon", {"id": taxon_id})
    objectify.SubElement(taxon, "date", {"value": str(date), "direction": direction, "units": units})


def get_alignment_block(xml_root, alignment_id, missing="-", sequence_type="nucleotide"):
    """
    Get an alignment block from a BEAST xml. If the alignment block does not exist, it will be
    created and inserted into `xml_root` (modified in place).
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    alignment_id : str
        ID of an alignment block.
    missing : str, optional
        Character(s) which indicate missing data (e.g., "-?").
    sequence_type : str, optional
        Type of sequence (e.g., nucleotide).
        
    Returns
    -------
    lxml.objectify.ObjectifiedElement
        The relevant alignment block.
    """
    # Find existing alignment blocks
    for alignment in xml_root.iterchildren("alignment"):
        if alignment.get("id") == alignment_id:
            return alignment
    
    # Not found, so create a new alignment block
    alignment = xml_root.makeelement(
        "alignment", 
        {"id": alignment_id, "missing": missing, "dataType": sequence_type}
    )
    
    # Find the most appropriate place to insert the new alignment block
    taxa = xml_root.find("taxa")
    alignments = xml_root.findall("alignment")
    
    if len(alignments) > 0:
        # Insert below the last existing alignment block
        alignments[-1].addnext(alignment)
    elif taxa is not None:
        # Insert below the <taxa> block
        taxa.addnext(alignment)
    else:
        # XML has no <taxa> or <alignment> blocks yet, so insert as the first element
        xml_root.insert(0, alignment)
    
    return alignment


def add_sequence_blocks(xml_root, taxon_id, sequences, missing="-", sequence_type="nucleotide"):
    """
    Add sequences for a single taxon to the <alignment> block(s) of a BEAST xml. Sequences 
    should be supplied as a dictionary, with keys corresponding to the ids of alignment blocks 
    in the xml file. If a given alignment block does not exist, it will be created.
    
    `xml_root` is modified in place.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    taxon_id : str
        Name of a taxon.
    sequences : dict
        Sequences for this taxon, keyed by alignment block name.
    missing : str, optional
        Character(s) which indicate missing data (e.g., "-?").
    sequence_type : str, optional
        Type of sequence (e.g., nucleotide).
        
    Returns
    -------
    None
    """
    for alignment_id, sequence in sequences.items():
        # Get alignment block
        alignment = get_alignment_block(
            xml_root, 
            alignment_id,
            missing=missing, 
            sequence_type=sequence_type
        )
                
        # Check if sequence is compatible with existing alignment
        _check_alignment_compatibility(
            alignment_block=alignment,
            sequence=sequence,
            missing=missing,
            sequence_type=sequence_type,
            alignment_id=alignment_id, 
            taxon_id=taxon_id
        )
        
        # Add sequence
        sequence_block = objectify.SubElement(alignment, "sequence")
        taxon_ref = objectify.SubElement(sequence_block, "taxon", {"idref": taxon_id})
        taxon_ref.tail = sequence  # Ensures that sequence follows taxon reference


def add_taxon(xml_root, taxon_id, date, sequences, missing="-",
              sequence_type="nucleotide",
              direction="forwards",
              units="years"):
    """
    Add a new taxon to a BEAST xml. This involves adding a new <taxon> element to the <taxa> 
    block specifying the sampling date, and adding sequence(s) for this taxon to the <alignment> 
    block(s).
    
    `xml_root` is modified in place.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    taxon_id : str
        Name of a taxon to add.
    date : float
        Sampling date associated with this taxon.
    sequences : dict
        Sequences for this taxon, keyed by alignment block name.
    missing : str, optional
        Character(s) which indicate missing data (e.g., "-?").
    sequence_type : str, optional
        Type of sequence (e.g., nucleotide).
    direction : str, optional
        Direction of time (forwards or backwards).
    units : str, optional
        Units of `time`. By default, this is "years", meaning `date` should be in decimal years.
        
    Returns
    -------
    None
    """
    add_taxon_block(xml_root, taxon_id, date, direction=direction, units=units)
    add_sequence_blocks(xml_root, taxon_id, sequences, missing=missing, sequence_type=sequence_type)
    

def add_unsampled_taxon(xml_root, taxon_id, date, 
                        missing="-", 
                        sequence_type="nucleotide", 
                        direction="forwards", 
                        units="years"):
    """
    Add an unsampled taxon to a BEAST xml file. A placeholder sequence consisting of missing data
    characters "N" will be added to all alignments in the XML.
    
    Each alignment in the XML should contain at least one sequence already, to allow the length
    of the unsampled sequence to be inferred.
    
    `xml_root` is modified in place.
    
    Parameters
    ----------
    xml_root : lxml.objectify.ObjectifiedElement
        Root of a BEAST xml, parsed using the lxml.objectify parser.
    taxon_id : str
        Name of a taxon to add.
    date : float
        Sampling date associated with this taxon.
    missing : str, optional
        Character(s) which indicate missing data (e.g., "-?").
    sequence_type : str, optional
        Type of sequence (e.g., nucleotide).
    direction : str, optional
        Direction of time (forwards or backwards).
    units : str, optional
        Units of `time`. By default, this is "years", meaning `date` should be in decimal years.
        
    Returns
    -------
    None
    """
    # Get alignment blocks
    alignment_blocks = xml_root.findall("alignment")
    alignment_blocks = {a.get("id"): a for a in alignment_blocks}
    
    if len(alignment_blocks) == 0:
        raise ValueError("At least one alignment block must be present in the XML file.")
    
    # Check that at least one sequence is present in each alignment block
    seq_lens = {}
    
    for alignment_id in alignment_blocks:
        alignment = alignment_blocks[alignment_id]
        
        valid = False
        
        if hasattr(alignment, "sequence"):
            if hasattr(alignment.sequence, "taxon"):
                if alignment.sequence.taxon.tail is not None:
                    valid = True
        
        if not valid:
            raise ValueError("At least one sequence must be present in each alignment block.")
    
    # Get sequence lengths
    seq_lens = {key: len(val.sequence.taxon.tail) for key, val in alignment_blocks.items()}
    
    # Generate sequences
    sequences = {key: "N" * val for key, val in seq_lens.items()}
    
    # Add taxon
    add_taxon_block(xml_root, taxon_id, date, direction=direction, units=units)
    add_sequence_blocks(xml_root, taxon_id, sequences, missing=missing, sequence_type=sequence_type)
