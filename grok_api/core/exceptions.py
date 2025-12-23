class GrokError(Exception):
    """Base exception for Grok API errors."""
    pass

class GrokNetworkError(GrokError):
    """Exception raised for network-related errors."""
    pass

class GrokParsingError(GrokError):
    """Exception raised when parsing response from Grok fails."""
    pass

class GrokAuthError(GrokError):
    """Exception raised for authentication or anti-bot issues."""
    pass

class GrokSessionError(GrokError):
    """Exception raised for session or cookie related issues."""
    pass
