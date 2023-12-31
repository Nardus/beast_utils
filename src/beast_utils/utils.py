# Utility functions for commonly-used tasks when working with BEAST analyses.

from datetime import datetime

def as_decimal_year(date):
    """
    Convert a date to decimal years.
    
    Parameters
    ----------
    date : str or datetime.date
        Date to convert. If string, must be in the format "YYYY-MM-DD".
        
    Returns
    -------
    float
        Decimal year.
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    year = date.year
    year_start = datetime(year=year, month=1, day=1)
    next_start = datetime(year=year+1, month=1, day=1)

    elapsed = date - year_start
    duration = next_start - year_start
    fraction = elapsed / duration

    return year + fraction


def set_value(xml_root, xpath, name, value):
    """
    Update or add a single attribute value in an XML file.
    
    `xml_root` will be modified in place.
    
    Parameters
    ----------
    xml_root : lxml.etree.ElementTree.Element
        The root element of the xml file.
    xpath : str
        An xpath query string defining the element to be modified.
    name : str
        The attribute name to be updated or added.
    value : any
        The value this attribute should be set to.
    
    Returns
    -------
    None
    """
    element = xml_root.find(xpath)
    
    if element is None:
        raise ValueError(f"No match found for xpath query {xpath}.")
    
    element.set(name, str(value))


def set_run_length(xml_root, run_length, n_samples=10000):
    """
    Update a BEAST xml to run for a given number of MCMC steps, adjusting log frequency to match. 
    This will update both the <mcmc> element and all <log> and <logTree> elements.
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : lxml.etree.ElementTree.Element
        The root element of the xml file.
    run_length : int
        The number of MCMC steps required.
    n_samples : int
        The number of samples to take (default: 10 000). This is used to set the log frequency.
    
    Returns
    -------
    None
    """
    run_length = int(run_length)
    n_samples = int(n_samples)
    
    log_frequency = run_length // n_samples

    # Update <mcmc> element:
    mcmc = xml_root.mcmc
    mcmc.set("chainLength", str(run_length))

    # Update all <log> elements:
    for log in mcmc.iterchildren("log"):
        log.set("logEvery", str(log_frequency))

    # Update all <logTree> elements:
    for log in mcmc.iterchildren("logTree"):
        log.set("logEvery", str(log_frequency))


def set_output_name(xml_root, stem):
    """
    Update a BEAST xml by completely replacing all log file names (apart from the extensions).
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : lxml.etree.ElementTree.Element
        The root element of the xml file.
    stem : str
        The file name stem to use for all log files. For example, if `stem` is "chain1", the
        log file names will be "chain1.log", "chain1.trees", etc.
    
    Returns
    -------
    None
    """
    # Update <mcmc> element:
    mcmc = xml_root.mcmc
    operators_file = mcmc.get("operatorAnalysis")

    if operators_file is not None:
        operators_extension = operators_file.split(".")[-1]
        mcmc.set("operatorAnalysis", f"{stem}.{operators_extension}")

    # Update all <log> elements:
    for log in mcmc.iterchildren("log"):
        cur_name = log.get("fileName")

        if cur_name is not None:
            cur_extension = cur_name.split(".")[-1]
            log.set("fileName", f"{stem}.{cur_extension}")

    # Update all <logTree> elements:
    for log in mcmc.iterchildren("logTree"):
        cur_name = log.get("fileName")

        if cur_name is not None:
            cur_extension = cur_name.split(".")[-1]
            log.set("fileName", f"{stem}.{cur_extension}")


def set_output_prefix(xml_root, prefix):
    """
    Update a BEAST xml by appending a prefix to all log file names.
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : lxml.etree.ElementTree.Element
        The root element of the xml file.
    prefix : str
        A prefix to add to all log file names.
    
    Returns
    -------
    None
    """
    # Update <mcmc> element:
    mcmc = xml_root.mcmc
    operators_file = mcmc.get("operatorAnalysis")
    
    if operators_file is not None:
        mcmc.set("operatorAnalysis", f"{prefix}.{operators_file}")

    # Update all <log> elements:
    for log in mcmc.iterchildren("log"):
        cur_name = log.get("fileName")
        
        if cur_name is not None:
            log.set("fileName", f"{prefix}.{cur_name}")

    # Update all <logTree> elements:
    for log in mcmc.iterchildren("logTree"):
        cur_name = log.get("fileName")
        
        if cur_name is not None:
            log.set("fileName", f"{prefix}.{cur_name}")


def extract_partition(alignment, indices):
    """
    Extract a partition from an alignment.
    
    Parameters
    ----------
    alignment : Bio.Align.MultipleSeqAlignment
        The alignment to extract from.
    indices : list of int
        The indices of alignment columns making up this partition.
        
    Returns
    -------
    Bio.Align.MultipleSeqAlignment
        The extracted partition.
    """
    # Need to use slice notation to get a single column as a MultipleSeqAlignment (and not a string)
    i = indices[0]
    partition = alignment[:, i:(i+1)]
    
    for i in indices[1:]:
        partition += alignment[:, i:(i+1)]
    
    return partition
