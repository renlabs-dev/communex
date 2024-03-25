

class AuthorizationError(Exception):
    """Access denied. Unathorized key."""

class ChainTransactionError(Exception):
    """Error processing chain transaction."""

class InsufficientBalanceError(Exception):
    """Insufficient balance on key."""

class InsufficientStakeError(Exception):
    """Insufficient stake."""

class InvalidClassError(Exception):
    """Invalid class."""

class InvalidIPError(Exception):
    """Invalid ip."""

class InvalidModuleError(Exception):
    """Invalid module."""

class InvalidParameterError(Exception):
    """Invalid parameter."""
    
class InvalidProposalIDError(Exception):
    """Invalid proposal id."""
    
class InvalidKeyFormatError(Exception):
    """Invalid key format."""

class MismatchedLengthError(Exception):
    """Mismatched length."""
    
class NetworkError(BaseException):
    """Base for any network related errors."""

class NetworkQueryError(NetworkError):
    """Network query error."""

class QueueEmptyError(NetworkError):
    """Queue empty error."""
    
class QueryError(NetworkError):
    """Generic query error."""

class SubstrateRequestException(Exception):
    """Substrate request exception."""

class CLIMenuError(Exception):
    """Base for any cli menu related errors."""

class CLIBalanceError(CLIMenuError):
    """Wrong command in balance cli menu."""

class CLIKeyError(CLIMenuError):
    """Wrong command in key cli menu."""   

class CLIMiscError(CLIMenuError):
    """Wrong command in misc cli menu."""

class CLIModuleError(CLIMenuError):
    """Wrong command in module cli menu."""

class CLINetworkError(CLIMenuError):
    """Wrong command in network cli menu."""

class CLISubnetError(CLIMenuError):
    """Wrong command in subnet cli menu."""