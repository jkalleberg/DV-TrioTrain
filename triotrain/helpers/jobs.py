from typing import Union


def is_jobid(value: Union[int, str]) -> bool:
    """Determine if a user entered value is a SLURM job id, indicating a currently running job to save for building job dependencies.

    Parameters
    ----------
    value : Union[int, str]
        the value to be checked

    Returns
    -------
    bool
        if True, entry is a valid SLURM job number
    """
    return len(str(value)) in [8] and str(value).isdigit()


def is_job_index(value: Union[int, str], max_jobs: int = 1) -> bool:
    """Determine if a user entered value is list index, indicating a job to be re-run.

    Parameters
    ----------
    value : Union[int, str]
        the value to be checked

    Returns
    -------
    bool
        if True, entry can be used to index a list of SLURM jobs
    """
    return str(value).isdigit() and 0 <= int(value) <= max_jobs
