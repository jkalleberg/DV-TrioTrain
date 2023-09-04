def process_resource(txt: str) -> str:
    """
    Handle any special characters and remove any separators.

    Input: 'A,Quick brown-fox jumped-over-the   lazy-dog'
    Output: 'AQuickbrownfoxjumpedoverthelazydog'
    """
    specialChars = "!#$%^&*()"
    for specialChar in specialChars:
        txt = txt.replace(specialChar, "")
    standardizeSeps = " -,_"
    for sep in standardizeSeps:
        txt = txt.replace(sep, "")
    return txt