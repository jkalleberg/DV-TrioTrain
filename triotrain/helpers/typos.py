"""
sauce: https://stackoverflow.com/questions/62106645/what-is-efficient-way-to-check-if-current-word-is-close-to-a-word-in-string"""

from Levenshtein import jaro_winkler


def check_typos(original_word: str, new_word: str) -> list:
    """checking if current word is close to another word

    Parameters
    ----------
    original_word : str
        value to compare againsts
    new_word : str
        compared for similarity to original value

    Returns
    -------
    List
        contains strings which were highly similar between str1 and str2
    """
    min_similarity = 0.75
    output = []
    results = [
        [jaro_winkler(x, y) for x in original_word.split()] for y in new_word.split()
    ]
    for x in results:
        if max(x) >= min_similarity:
            output.append(original_word.split()[x.index(max(x))])
    return output
