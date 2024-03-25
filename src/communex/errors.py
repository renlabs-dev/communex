class AuthorizationError(Exception):
    """Error for any authorization related errors."""

class ChainTransactionError(Exception):
    """Error for any chain transaction related errors."""

class InsufficientBalanceError(Exception):
    """Insufficient balance related error."""

class InsufficientStakeError(Exception):
    """Insufficient stake related error."""

class InvalidClassError(Exception):
    """Invalid class related error."""

class InvalidIPError(Exception):
    """Invalid ip related error."""

class InvalidModuleError(Exception):
    """Invalid module related error."""

class InvalidParameterError(Exception):
    """Invalid parameter related error."""
    
class InvalidProposalIDError(Exception):
    """Invalid proposal id related error."""
    
class KeyFormatError(Exception):
    """Key format related error."""
    
class NetworkError(BaseException):
    """Base for any network related errors."""

class NetworkQueryError(NetworkError):
    """Network query related error."""

class QueryError(NetworkError):
    """Query related error."""
    
class MismatchedLengthError(Exception):
    """Mismatched length related error."""

class CLIBalanceError(Exception):
    """Wrong command for balance cli menu."""

class CLIKeyError(Exception):
    """Wrong command for key cli menu."""   

class CLIMiscError(Exception):
    """Wrong command for misc cli menu."""

class CLIModuleError(Exception):
    """Wrong command for module cli menu."""

class CLINetworkError(Exception):
    """Wrong command for network cli menu."""

class CLISubnetError(Exception):
    """Wrong command for subnet cli menu."""