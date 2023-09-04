def process_phase(txt: str) -> str:
    """
    Handle any special characters and only use '_' as a separator.

    Input: 'A,Quick brown-fox jumped-over-the   lazy-dog'
    Output: 'A_Quick_brown_fox_jumped_over_the_lazy_dog'
    """
    special_chars = "!#$%^&*()"
    for special_char in special_chars:
        txt = txt.replace(special_char, "")
    standardize_seps = " -,"
    for sep in standardize_seps:
        txt = txt.replace(sep, "_")
    return txt