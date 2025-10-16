"""
SCLib_Auth - Standalone Authentication and Authorization Module
Provides JWT-based authentication using Auth0 for ScientistCloud.
Completely independent of Bokeh authorization and other SCLib components.
"""

# Main standalone authentication API
from .SCLib_AuthAPI_Standalone import app as auth_api_app

# Core authentication components (optional - for advanced usage)
try:
    from .SCLib_AuthManager import SCLib_AuthManager, get_auth_manager
    from .SCLib_JWTManager import SCLib_JWTManager, get_jwt_manager
    from .SCLib_UserManager import SCLib_UserManager, get_user_manager
    from .SCLib_AuthMiddleware import (
        SCLib_AuthMiddleware, get_auth_middleware,
        require_auth, optional_auth, get_current_user, 
        get_current_user_email, get_current_user_id,
        setup_auth_middleware, AuthResult
    )
    ADVANCED_AUTH_AVAILABLE = True
except ImportError:
    ADVANCED_AUTH_AVAILABLE = False

__all__ = [
    'auth_api_app',  # Main standalone FastAPI app
]

if ADVANCED_AUTH_AVAILABLE:
    __all__.extend([
        'SCLib_AuthManager',
        'get_auth_manager',
        'SCLib_JWTManager', 
        'get_jwt_manager',
        'SCLib_UserManager',
        'get_user_manager',
        'SCLib_AuthMiddleware',
        'get_auth_middleware',
        'require_auth',
        'optional_auth',
        'get_current_user',
        'get_current_user_email',
        'get_current_user_id',
        'setup_auth_middleware',
        'AuthResult'
    ])
