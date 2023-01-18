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
