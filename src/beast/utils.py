# Utility functions for commonly-used tasks when working with BEAST analyses.

from datetime import datetime

def as_decimal_year(date):
    """
    Convert a date to decimal years.
    
    Parameters
    ----------
    date : datetime.date
        Date to convert.
        
    Returns
    -------
    float
        Decimal year.
    """
    year = date.year
    year_start = datetime(year=year, month=1, day=1)
    next_start = datetime(year=year+1, month=1, day=1)

    elapsed = date - year_start
    duration = next_start - year_start
    fraction = elapsed / duration

    return year + fraction


def set_run_length(xml_root, run_length, n_samples=10000):
    """
    Update a BEAST xml to run for a given number of MCMC steps, adjusting log frequency to match. 
    This will update both the <mcmc> element and all <log> and <logTree> elements.
    
    `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    run_length : int
        The number of MCMC steps required.
    n_samples : int
        The number of samples to take (default: 10 000). This is used to set the log frequency.
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
