"""
Cloudflare verification module for BattyCoda

This module provides functions to verify that requests are coming through Cloudflare
and that they have valid Cloudflare Access JWT tokens if access protection is enabled.
"""

import os
import logging
import jwt
import requests
from functools import wraps
from flask import request, abort, current_app

# Set up logging
logger = logging.getLogger('battycoda.cloudflare')

# Cache for the Cloudflare certificates
_cf_certs = None
_cf_certs_last_updated = 0

def get_cloudflare_certs(audience):
    """
    Fetch Cloudflare certificates needed for JWT validation
    """
    global _cf_certs, _cf_certs_last_updated
    import time
    
    # Only fetch every hour
    current_time = time.time()
    if _cf_certs and current_time - _cf_certs_last_updated < 3600:
        logger.debug("Using cached Cloudflare certificates")
        return _cf_certs
    
    try:
        # Try multiple different URL formats that Cloudflare might use
        urls_to_try = []
        
        # 1. Get domain from environment variable or use a default
        cloudflare_domain = os.environ.get('CLOUDFLARE_DOMAIN', 'battycoda.com')
        
        # 2. Add standard URL format for the domain
        urls_to_try.append(f"https://{cloudflare_domain}/cdn-cgi/access/certs")
        
        # 3. Add team subdomain format
        team_name = cloudflare_domain.split('.')[0]
        urls_to_try.append(f"https://{team_name}.cloudflareaccess.com/cdn-cgi/access/certs")
        
        # 4. Try the audience directly as a domain
        if audience and '.' in audience:
            urls_to_try.append(f"https://{audience}/cdn-cgi/access/certs")
        
        # 5. Try the Cloudflare Teams format
        urls_to_try.append(f"https://{team_name}.cloudflareaccess.com/cdn-cgi/access/cert")
        
        logger.info(f"Will try the following certificate URLs: {urls_to_try}")
        
        # Try each URL until we get a valid response
        for cert_url in urls_to_try:
            try:
                logger.info(f"Attempting to fetch Cloudflare certificates from: {cert_url}")
                response = requests.get(cert_url)
                
                # Log response details for debugging
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                
                if response.status_code == 200:
                    try:
                        cert_data = response.json()
                        # Validate that we got a proper JWKS
                        if 'keys' in cert_data and isinstance(cert_data['keys'], list) and len(cert_data['keys']) > 0:
                            logger.info(f"Successfully fetched Cloudflare certificates from {cert_url}")
                            _cf_certs = cert_data
                            _cf_certs_last_updated = current_time
                            return _cf_certs
                        else:
                            logger.warning(f"Response from {cert_url} was 200 but did not contain valid JWKS data")
                    except ValueError:
                        logger.warning(f"Response from {cert_url} was not valid JSON")
                else:
                    logger.warning(f"Failed to fetch from {cert_url}: {response.status_code}")
            except Exception as url_err:
                logger.warning(f"Error fetching from {cert_url}: {str(url_err)}")
        
        # If we get here, all URLs failed
        logger.error("All certificate URLs failed, could not fetch Cloudflare certificates")
        return _cf_certs  # Return cached certs if available, otherwise None
    except Exception as e:
        logger.error(f"Unexpected error in get_cloudflare_certs: {str(e)}")
        return _cf_certs  # Return cached certs if available, otherwise None

def verify_cloudflare_headers():
    """
    Verify that the request includes Cloudflare headers
    
    Returns:
        bool: True if the request has Cloudflare headers, False otherwise
    """
    # Check for essential Cloudflare headers
    cf_connecting_ip = request.headers.get('CF-Connecting-IP')
    cf_ray = request.headers.get('CF-Ray')
    
    # If these headers aren't present, connection is likely not from Cloudflare
    if not cf_connecting_ip or not cf_ray:
        logger.warning(f"Request missing Cloudflare headers: IP={request.remote_addr}")
        return False
    
    logger.debug(f"Request verified from Cloudflare: CF-Connecting-IP={cf_connecting_ip}, CF-Ray={cf_ray}")
    return True

def verify_cloudflare_jwt():
    """
    Verify Cloudflare Access JWT token
    
    Returns:
        dict: User information from the JWT token if valid
        None: If token is invalid or not present
    """
    if not os.environ.get('CLOUDFLARE_ACCESS_ENABLED') == 'True':
        return None
    
    audience = os.environ.get('CLOUDFLARE_AUDIENCE')
    if not audience:
        logger.error("CLOUDFLARE_AUDIENCE not set but CLOUDFLARE_ACCESS_ENABLED is True")
        return None
    
    # Get the JWT token from the request
    cf_token = request.cookies.get('CF_Authorization')
    cf_header_token = request.headers.get('CF-Access-Jwt-Assertion')
    
    logger.debug(f"Looking for Cloudflare tokens - Cookie: {'Present' if cf_token else 'None'}, Header: {'Present' if cf_header_token else 'None'}")
    
    # Try header if cookie is missing
    if not cf_token and cf_header_token:
        logger.info("Using token from CF-Access-Jwt-Assertion header instead of cookie")
        cf_token = cf_header_token
    
    if not cf_token:
        logger.warning("No Cloudflare authorization token found in cookies or headers")
        return None
    
    # Get Cloudflare certificates
    certs = get_cloudflare_certs(audience)
    if not certs:
        logger.error("Could not fetch Cloudflare certificates for JWT validation")
        return None
    
    # Try to validate the token
    try:
        # Get the JWT header to find the key ID (kid)
        header = jwt.get_unverified_header(cf_token)
        logger.debug(f"JWT header: {header}")
        kid = header.get('kid')
        
        if not kid:
            logger.error("No 'kid' found in JWT header")
            return None
            
        # Find the matching key in the JWK set
        if 'keys' not in certs:
            logger.error(f"Unexpected certificate format. Expected JWK set with 'keys' array, got: {certs.keys()}")
            return None
            
        rsa_key = None
        for key in certs['keys']:
            if key.get('kid') == kid:
                rsa_key = key
                break
                
        if not rsa_key:
            logger.error(f"No matching key found for kid: {kid}")
            return None
        
        # Convert JWK to PEM using PyJWT utilities
        try:
            from jwt.algorithms import RSAAlgorithm
            public_key = RSAAlgorithm.from_jwk(rsa_key)
        except Exception as jwk_err:
            logger.error(f"Error converting JWK to PEM: {str(jwk_err)}")
            return None
            
        # Now validate the token with the proper key
        jwt_payload = jwt.decode(
            cf_token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            options={"verify_exp": True}
        )
        
        logger.info(f"Valid Cloudflare JWT for user: {jwt_payload.get('email')}")
        return jwt_payload
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid Cloudflare JWT: {str(e)}")
        # Log the full error details for debugging
        logger.debug(f"JWT validation error details: {str(e)}")
        return None

def require_cloudflare(f):
    """
    Decorator to require requests to come through Cloudflare
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip verification in development mode
        if current_app.config.get('FLASK_ENV') == 'development' and not os.environ.get('ENFORCE_CLOUDFLARE_IN_DEV'):
            return f(*args, **kwargs)
        
        if not verify_cloudflare_headers():
            logger.warning(f"Blocking direct access attempt from {request.remote_addr}")
            abort(403, "Direct access to this server is not allowed. Please access through Cloudflare.")
        
        return f(*args, **kwargs)
    return decorated_function

def require_cloudflare_access(f):
    """
    Decorator to require valid Cloudflare Access JWT
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip verification in development mode
        if current_app.config.get('FLASK_ENV') == 'development' and not os.environ.get('ENFORCE_CLOUDFLARE_IN_DEV'):
            return f(*args, **kwargs)
        
        # First verify it's coming through Cloudflare
        if not verify_cloudflare_headers():
            logger.warning(f"Blocking direct access attempt from {request.remote_addr}")
            abort(403, "Direct access to this server is not allowed. Please access through Cloudflare.")
        
        # Then verify Cloudflare Access JWT if enabled
        if os.environ.get('CLOUDFLARE_ACCESS_ENABLED') == 'True':
            jwt_payload = verify_cloudflare_jwt()
            if not jwt_payload:
                logger.warning(f"Invalid or missing Cloudflare Access JWT from {request.remote_addr}")
                abort(401, "Authentication required. Please log in through Cloudflare Access.")
            
            # Store user info in request object for later use
            request.cloudflare_user = jwt_payload
        
        return f(*args, **kwargs)
    return decorated_function