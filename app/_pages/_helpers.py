# _helpers.py

def _remove_small_zeros(num_str: str) -> str:
    """A number on a string, formatted to 6 decimal places.
    is parsed and the 0 on the right are removed until the units position.
    """
    try:
        # Parse the string as a float and format it
        return num_str.rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return num_str

