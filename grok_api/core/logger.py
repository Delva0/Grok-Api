from typing      import Optional
from datetime    import datetime
from colorama    import Fore
from threading   import Lock
from time        import time


class Log:
    """
    Logging class to log text better in console.
    """
    
    enabled: bool = False
    
    colours: Optional[dict] = {
        'SUCCESS': Fore.LIGHTGREEN_EX,
        'ERROR': Fore.LIGHTRED_EX,
        'INFO': Fore.LIGHTWHITE_EX
    }
    
    lock = Lock()
    
    @classmethod
    def set_enabled(cls, enabled: bool) -> None:
        """
        Enable or disable logging.
        
        :param enabled: True to enable, False to disable.
        """
        cls.enabled = enabled

    @staticmethod
    def _log(level, prefix, message) -> Optional[None]:
        """
        Private log function to build the payload to print.
        
        :param level: Just not used, only a filler
        :param prefix: Prefix to indicate if its Success, Error or Info
        :param message: Message to Log
        """
        
        if not Log.enabled:
            return
        
        timestamp: Optional[int] = datetime.fromtimestamp(time()).strftime("%H:%M:%S")
        
        log_message = (
            f"{Fore.LIGHTBLACK_EX}[{Fore.MAGENTA}{timestamp}{Fore.RESET}{Fore.LIGHTBLACK_EX}]{Fore.RESET} "
            f"{prefix} {message}"
        )
        
        with Log.lock:
            print(log_message)

    @staticmethod
    def Success(message, prefix="[+]", color=colours['SUCCESS']) -> Optional[None]:
        """
        Logging a Success message.
        """
        Log._log("SUCCESS", f"{color}{prefix}{Fore.RESET}", message)

    @staticmethod
    def Error(message, prefix="[!]", color=colours['ERROR']) -> Optional[None]:
        """
        Logging an Error Message.
        """
        Log._log("ERROR", f"{color}{prefix}{Fore.RESET}", message)

    @staticmethod
    def Info(message, prefix="[!]", color=colours['INFO']) -> Optional[None]:
        """
        Logging an Info Message.
        """
        Log._log("INFO", f"{color}{prefix}{Fore.RESET}", message)