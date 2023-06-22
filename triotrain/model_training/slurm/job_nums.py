def collect_job_nums(dependency_list: List[str], allow_dep_failure: bool = False):
    """
    Function to format Slurm Job Numbers into SLURM dependency strings.
    """
    not_none_values = filter(None, dependency_list)
    complete_list = list(not_none_values)
    prep_jobs = ":".join(complete_list)
    if allow_dep_failure:
        list_dependency = [
            f"--dependency=afterany:{prep_jobs}",
            "--kill-on-invalid-dep=yes",
        ]
    else:
        list_dependency = [
            f"--dependency=afterok:{prep_jobs}",
            "--kill-on-invalid-dep=yes",
        ]
    return list_dependency
