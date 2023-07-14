from typing import List, Union


def collect_job_nums(
    dependency_list: List[Union[str, None]], allow_dep_failure: bool = False
) -> List[str]:
    """Format a list of Slurm job numbers into a SLURM dependency string, and build command flags for SBATCH.

    Parameters
    ----------
    dependency_list : List[str]
        contains 8-digit SLURM job numbers, uses 'None' as a placeholder; downstream jobs will run when these jobs finish
    allow_dep_failure : bool, optional
        if True, allow downstream jobs to start even if dependency returns a non-zero exit code; by default False

    Returns
    -------
    dependency_cmd: List[str]
        contains the SBATCH flags for job dependency
    """
    not_none_values = filter(None, dependency_list)
    complete_list = list(not_none_values)
    prep_jobs = ":".join(complete_list)
    if allow_dep_failure:
        dependency_cmd = [
            f"--dependency=afterany:{prep_jobs}",
            "--kill-on-invalid-dep=yes",
        ]
    else:
        dependency_cmd = [
            f"--dependency=afterok:{prep_jobs}",
            "--kill-on-invalid-dep=yes",
        ]
    return dependency_cmd
