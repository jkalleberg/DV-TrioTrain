def remove_suffixes(filename: Path, remove_all: bool = True) -> Path:
    """
    Removing multiple file suffixes.
    """
    if not remove_all:
        suffixes = {".gz"}
    else:
        suffixes = {".bcf", ".vcf", ".gz"}
    while filename.suffix in suffixes:
        filename = filename.with_suffix("")

    return filename