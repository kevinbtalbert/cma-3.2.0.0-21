#!/usr/bin/python
import sys


def convert_time_to_seconds(t: str) -> int:
    """
    Valid Time Formats: 10, 35s, 17m, 21h, 7d
    Invalid Time Formats: 10d4h
    Documentation: https://docs.oracle.com/cd/E19253-01/816-5174/6mbb98ufn/index.html
    """
    unit = str(t[-1:])
    units = {
        's': 1,
        'm': 60,
        'h': 60 * 60,
        'd': 60 * 60 * 24
    }

    if unit.isdigit() and int(t) >= 0:
        return int(t)

    if unit in units and int(t[:-1]) >= 0:
        return int(t[:-1]) * units.get(unit)

    raise Exception("Invalid time format {0}, cannot convert to seconds".format(t))
