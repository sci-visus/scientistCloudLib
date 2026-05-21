"""
Authentication utilities for Bokeh dashboards
"""
import os
import jwt
from dotenv import load_dotenv
from utils_bokeh_mongodb import connect_to_mongodb, check_dataset_access

# Load environment variables
load_dotenv()

def get_cookie_from_request(cookie_name, request=None, status_callback=None):
    """Get cookie value from Bokeh request - matches your 4d_dashboard.py implementation"""
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    add_status(f"🔍 Looking for cookie: {cookie_name}")
    
    try:
        if request is None:
            # Get the current Bokeh document/request
            from bokeh.io import curdoc
            doc = curdoc()
            
            if hasattr(doc, 'session_context') and doc.session_context:
                request = doc.session_context.request
                add_status(f"🔍 DEBUG: Got request from session_context")
            else:
                add_status(f"❌ No session context available in Bokeh document")
                return None
        
        # Debug: Check what we have in the request
        # add_status(f"🔍 DEBUG: request type: {type(request)}")
        # add_status(f"🔍 DEBUG: request has cookies: {hasattr(request, 'cookies')}")
        # if hasattr(request, 'cookies'):
        #     add_status(f"🔍 DEBUG: cookies type: {type(request.cookies)}")
        #     add_status(f"🔍 DEBUG: cookies content: {request.cookies}")
        # if hasattr(request, 'headers'):
        #     add_status(f"🔍 DEBUG: headers type: {type(request.headers)}")
        #     add_status(f"🔍 DEBUG: headers content: {request.headers}")
        
        if hasattr(request, 'cookies') and request.cookies:
            # Try different ways to access the cookie
            try:
                # Method 1: Direct dictionary access
                if hasattr(request.cookies, '__getitem__'):
                    cookie_value = request.cookies[cookie_name]
                    add_status(f"✅ Found cookie '{cookie_name}' ...")
                    return str(cookie_value)
            except (KeyError, TypeError) as e:
                add_status(f"❌ Method 1 failed: {e}")
            
            try:
                # Method 2: get() method
                if hasattr(request.cookies, 'get'):
                    cookie_value = request.cookies.get(cookie_name)
                    if cookie_value:
                        add_status(f"✅ Found cookie '{cookie_name}' ...")
                        return str(cookie_value)
            except Exception as e:
                add_status(f"❌ Method 2 failed: {e}")
            
            try:
                # Method 3: Check if it's a list and convert to dict
                if isinstance(request.cookies, list):
                    add_status(f"🔍 Cookies is a list, trying to access as dict...")
                    # Try to access as dict anyway
                    cookie_value = request.cookies[cookie_name]
                    add_status(f"✅ Found cookie '{cookie_name}'  ...")
                    return str(cookie_value)
            except (KeyError, TypeError) as e:
                add_status(f"❌ Method 3 failed: {e}")
            
            add_status(f"❌ Cookie '{cookie_name}' not found in available cookies")
        else:
            add_status(f"❌ No cookies found in Bokeh request")
            
    except Exception as e:
        add_status(f"❌ Error getting cookie: {e}")
    
    return None

def get_portal_user_email_from_headers(request=None, status_callback=None):
    """Email passed by nginx after portal auth_request (when auth_token cookie is missing)."""
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)

    if request is None:
        return None
    try:
        headers = getattr(request, "headers", None)
        if not headers:
            return None
        for key in ("X-SC-User-Email", "X-Sc-User-Email", "x-sc-user-email"):
            val = None
            if hasattr(headers, "get"):
                val = headers.get(key)
            if val is None and hasattr(headers, "__getitem__"):
                try:
                    val = headers[key]
                except (KeyError, TypeError):
                    pass
            if val:
                email = str(val).strip()
                if email and "@" in email:
                    add_status(f"✅ Portal user from header: {email}")
                    return email
    except Exception as e:
        add_status(f"❌ Error reading portal user header: {e}")
    return None


def get_auth0_session_cookie(request=None, status_callback=None):
    """Get Auth0 session cookie - tries multiple possible cookie names"""
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    # List of possible Auth0 session cookie names
    possible_cookies = [
        'auth_token',           # Original expected name
        'auth0_session_0',      # Auth0 session cookie
        'auth0_session',        # Alternative Auth0 session cookie
        'auth0.is.authenticated', # Auth0 authentication cookie
        'auth0_session_1',      # Additional session cookie
        'auth0_session_2',      # Additional session cookie
    ]
    
    add_status("🔍 Looking for Auth0 session cookies...")
    
    for cookie_name in possible_cookies:
        cookie_value = get_cookie_from_request(cookie_name, request, status_callback)
        if cookie_value:
            add_status(f"✅ Found Auth0 session cookie: {cookie_name}")
            return cookie_value
    
    add_status("❌ No Auth0 session cookies found")
    return None

def get_auth_token_from_cookies(request=None, status_callback=None):
    """Get authentication token from various possible cookie sources"""
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    # Debug: List all available cookies
    if request and hasattr(request, 'cookies') and request.cookies:
        add_status("🔍 Available cookies:")
        try:
            if hasattr(request.cookies, 'keys'):
                for cookie_name in request.cookies.keys():
                    add_status(f"   - {cookie_name}")
            elif isinstance(request.cookies, dict):
                for cookie_name in request.cookies:
                    add_status(f"   - {cookie_name}")
        except Exception as e:
            add_status(f"   Error listing cookies: {e}")
    
    # First try the original auth_token
    auth_token = get_cookie_from_request('auth_token', request, status_callback)
    if auth_token:
        add_status("✅ Found auth_token cookie")
        return auth_token
    
    # If not found, try Auth0 session cookies
    auth0_cookie = get_auth0_session_cookie(request, status_callback)
    if auth0_cookie:
        add_status("✅ Found Auth0 session cookie")
        # Auth0 session cookies contain session data, not JWT tokens
        # We need to handle this differently - for now, return None to indicate
        # that we found a session but it's not a JWT token
        add_status("⚠️ Auth0 session cookie found but not a JWT token")
        return None
    
    add_status("❌ No authentication cookies found")
    return None

def decode_jwt_token(token, secret_key):
    """Decode and validate portal dashboard JWT (auth_token cookie)."""
    env_aud = (os.getenv("AUTH0_AUDIENCE") or "").strip()
    audiences = ["sclib-api"]
    if env_aud and env_aud not in audiences:
        audiences.append(env_aud)
    # Legacy portal cookies minted with AUTH0_AUDIENCE as JWT aud (e.g. old deploy server URL)
    legacy_aud = (os.getenv("DEPLOY_SERVER") or "").strip().rstrip("/")
    if legacy_aud and legacy_aud not in audiences:
        audiences.append(legacy_aud)

    last_error = None
    for aud in audiences:
        try:
            decoded = jwt.decode(
                token,
                secret_key,
                algorithms=["HS256"],
                audience=aud,
                issuer="sclib-auth",
            )
            return decoded, None
        except jwt.ExpiredSignatureError as e:
            return None, f"JWT token expired: {e}"
        except jwt.InvalidTokenError as e:
            last_error = e

    try:
        decoded = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
        return decoded, None
    except jwt.ExpiredSignatureError as e:
        return None, f"JWT token expired: {e}"
    except jwt.InvalidTokenError as e:
        return None, f"Invalid JWT token: {e}"
    except Exception as e:
        return None, f"Authentication error: {e}"

    if last_error:
        return None, f"Invalid JWT token: {last_error}"
    return None, "Invalid JWT token"

def authenticate_user(uuid, request=None, status_callback=None):
    """
    Authenticate user and return authentication result
    
    Args:
        uuid: Dataset UUID
        request: Bokeh request object (optional)
        status_callback: Function to call with status messages (optional)
    
    Returns:
        dict: {
            'is_authorized': bool,
            'user_email': str or None,
            'access_type': str,  # 'public', 'direct', 'team', 'none', 'error'
            'error': str or None
        }
    """
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    try:
        # Get secret key
        secret_key = os.getenv('SECRET_KEY')
        add_status(f"🔍 DEBUG: SECRET_KEY available: {bool(secret_key)}")
        if secret_key:
            add_status(f"🔍 DEBUG: SECRET_KEY length: {len(secret_key)}")
        if not secret_key:
            add_status("❌ Secret key not configured")
            return {
                'is_authorized': False,
                'user_email': None,
                'access_type': 'error',
                'error': 'Secret key not configured'
            }
        
        # Connect to MongoDB
        client, db, collection, collection1, team_collection, shared_team_collection = connect_to_mongodb()
        if not client:
            add_status("❌ MongoDB connection failed")
            return {
                'is_authorized': False,
                'user_email': None,
                'access_type': 'error',
                'error': 'MongoDB connection failed'
            }
        
        # Check if dataset is public
        is_authorized, access_type, message = check_dataset_access(
            collection, collection1, team_collection, shared_team_collection, uuid, None, is_public=True
        )
        
        if is_authorized:
            add_status("✅ Accessing public dataset")
            return {
                'is_authorized': True,
                'user_email': None,
                'access_type': 'public',
                'error': None
            }
        
        # Get auth token - try multiple cookie sources
        add_status(f"🔍 Looking for auth token for dataset: {uuid}")
        auth_token = get_auth_token_from_cookies(request, status_callback)
        add_status(f"🔍 DEBUG: auth_token extracted: {bool(auth_token)}")
        if auth_token:
            add_status(f"🔍 DEBUG: auth_token length: {len(auth_token)}")
            add_status(f"🔍 DEBUG: auth_token preview: {auth_token[:50]}...")
        
        if not auth_token:
            portal_email = get_portal_user_email_from_headers(request, status_callback)
            if portal_email:
                is_authorized, access_type, message = check_dataset_access(
                    collection, collection1, team_collection, shared_team_collection,
                    uuid, portal_email,
                )
                if is_authorized:
                    add_status(f"✅ {message}")
                    return {
                        'is_authorized': True,
                        'user_email': portal_email,
                        'access_type': access_type,
                        'message': message,
                        'error': None,
                    }
                add_status(f"❌ {message}")
                return {
                    'is_authorized': False,
                    'user_email': portal_email,
                    'access_type': access_type,
                    'message': message,
                    'error': message,
                }

            auth0_cookie = get_auth0_session_cookie(request, status_callback)
            if auth0_cookie:
                add_status("✅ Found Auth0 session - treating as authenticated")
                return {
                    'is_authorized': True,
                    'user_email': 'auth0_session_user',
                    'access_type': 'auth0_session',
                    'error': None
                }

            add_status("❌ No auth token or session found")
            return {
                'is_authorized': False,
                'user_email': None,
                'access_type': 'none',
                'error': 'No auth token or session found'
            }
        
        # Decode JWT token
        add_status(f"🔍 DEBUG: Attempting to decode JWT token...")
        decoded, error = decode_jwt_token(auth_token, secret_key)
        if error:
            add_status(f"❌ JWT decode error: {error}")
            return {
                'is_authorized': False,
                'user_email': None,
                'access_type': 'error',
                'error': error
            }
        
        add_status(f"🔍 DEBUG: JWT decoded successfully")
        add_status(f"🔍 DEBUG: decoded payload: {decoded}")
        user_email = decoded.get('user') or decoded.get('email')
        if not user_email:
            add_status("❌ JWT missing user/email claim")
            return {
                'is_authorized': False,
                'user_email': None,
                'access_type': 'error',
                'error': "Missing 'user' or 'email' field in JWT token"
            }
        add_status(f"🔍 DEBUG: extracted user_email: {user_email}")
        add_status(f"✅ Authenticated user: {user_email}")
        
        # Check dataset access
        is_authorized, access_type, message = check_dataset_access(
            collection, collection1, team_collection, shared_team_collection, uuid, user_email
        )
        
        if is_authorized:
            add_status(f"✅ {message}")
            return {
                'is_authorized': True,
                'user_email': user_email,
                'access_type': access_type,
                'message': message,
                'error': None
            }
        else:
            add_status(f"❌ {message}")
            return {
                'is_authorized': False,
                'user_email': user_email,
                'access_type': access_type,
                'message': message,
                'error': message
            }
            
    except Exception as e:
        add_status(f"❌ Authentication error: {e}")
        return {
            'is_authorized': False,
            'user_email': None,
            'access_type': 'error',
            'error': str(e)
        }
