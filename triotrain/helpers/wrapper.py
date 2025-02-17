from datetime import datetime

def timestamp():
    """
    Provide the current time in human readable format.
    """
    current_datetime = datetime.now()
    formatted_time = current_datetime.strftime("%Y-%m-%d  %H:%M:%S")
    return str(formatted_time)


class Wrapper:
    """Displays whenever a script begins or finishes, creates boundaries for debugging.
    """

    def __init__(self, name: str, message: str) -> None:
        """Create a boundary for the current script

        Parameters
        ----------
        name : str
            current script name
        message : str
            either start or end of the script
        """
        self.name = name
        self.message = message

    def wrap_script(self, time: timestamp) -> None:
        """Create a script boundary with the current timestamp

        Parameters
        ----------
        timestamp : str
            formatted datetime stamp indiciating when reaching a script boundary
        """
        print(f"===== {self.message} of {self.name} @ {time} =====")
