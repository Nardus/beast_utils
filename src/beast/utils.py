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
