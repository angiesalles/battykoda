"""
Cloudflare verification middleware for BattyCoda Django application

This middleware verifies that requests are coming through Cloudflare
and that they have valid Cloudflare Access JWT tokens if access protection is enabled.
"""

import os
import logging
import time
import jwt
import requests
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import login
from django.contrib.auth.models import User
from battycoda_app.models import UserProfile
from django.utils import timezone

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
    
    # Only fetch every hour
    current_time = time.time()
    if _cf_certs and current_time - _cf_certs_last_updated < 3600:
        logger.debug("Using cached Cloudflare certificates")
        return _cf_certs
    
    try:
        # Try multiple different URL formats that Cloudflare might use
        urls_to_try = []
        
        # 1. Get domain from settings or environment variable
        cloudflare_domain = settings.CLOUDFLARE_DOMAIN
        
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

def verify_cloudflare_headers(request):
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
        logger.warning(f"Request missing Cloudflare headers: IP={request.META.get('REMOTE_ADDR')}")
        return False
    
    logger.debug(f"Request verified from Cloudflare: CF-Connecting-IP={cf_connecting_ip}, CF-Ray={cf_ray}")
    return True

def verify_cloudflare_jwt(request):
    """
    Verify Cloudflare Access JWT token
    
    Returns:
        dict: User information from the JWT token if valid
        None: If token is invalid or not present
    """
    if not settings.CLOUDFLARE_ACCESS_ENABLED:
        return None
    
    audience = settings.CLOUDFLARE_AUDIENCE
    if not audience:
        logger.error("CLOUDFLARE_AUDIENCE not set but CLOUDFLARE_ACCESS_ENABLED is True")
        return None
        
    # Log the audience we're using for debugging
    logger.warning(f"Using Cloudflare audience: {audience}")
    
    # Get the JWT token from the request
    cf_token = request.COOKIES.get('CF_Authorization')
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

class CloudflareAccessMiddleware:
    """
    Django middleware to verify Cloudflare Access authentication
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check if we should enforce Cloudflare access
        if settings.CLOUDFLARE_ACCESS_ENABLED:
            # Skip authentication for some paths
            skip_paths = ['/admin/']
            for path in skip_paths:
                if request.path.startswith(path):
                    return self.get_response(request)
                    
            # DISABLED for now - Always enforce Cloudflare verification
            # if settings.DEBUG and not os.environ.get('ENFORCE_CLOUDFLARE_IN_DEV'):
            #     # For development, just log the request would be verified
            #     logger.debug(f"Debug mode: Skipping Cloudflare verification for {request.path}")
            #     return self.get_response(request)
            
            # First verify the request is coming through Cloudflare
            if not verify_cloudflare_headers(request):
                logger.warning(f"Blocking direct access attempt to {request.path} from {request.META.get('REMOTE_ADDR')}")
                return HttpResponseForbidden("Direct access to this server is not allowed. Please access through Cloudflare.")
            
            # Next, verify the Cloudflare Access JWT
            jwt_payload = verify_cloudflare_jwt(request)
            if not jwt_payload:
                logger.warning(f"Invalid or missing Cloudflare Access JWT for {request.path} from {request.META.get('REMOTE_ADDR')}")
                # Redirect to login page instead of returning 401
                # Use battycoda_app:login to match the app's URL pattern
                try:
                    login_url = reverse('battycoda_app:login')
                except:
                    # Fallback to absolute URL if reverse fails
                    login_url = '/accounts/login/'
                return HttpResponseRedirect(login_url)
            
            # Store Cloudflare user info in the request
            request.cloudflare_user = jwt_payload
            
            # Auto-login user based on Cloudflare JWT
            if not request.user.is_authenticated:
                email = jwt_payload.get('email')
                cloudflare_id = jwt_payload.get('sub')
                
                if email:
                    try:
                        # First try to find user by Cloudflare ID in profile
                        try:
                            profile = UserProfile.objects.get(cloudflare_id=cloudflare_id)
                            user = profile.user
                            logger.info(f"Found existing user by Cloudflare ID: {cloudflare_id}")
                        except UserProfile.DoesNotExist:
                            # Next try to find by email
                            try:
                                user = User.objects.get(email=email)
                                # Update Cloudflare info for existing user
                                user.profile.cloudflare_id = cloudflare_id
                                user.profile.is_cloudflare_user = True
                                user.profile.cloudflare_email = email
                                user.profile.save()
                                logger.info(f"Updated existing user with Cloudflare info: {email}")
                            except User.DoesNotExist:
                                # Create new user
                                username = email.split('@')[0].replace('.', '_')
                                # Ensure username is unique
                                i = 1
                                temp_username = username
                                while User.objects.filter(username=temp_username).exists():
                                    temp_username = f"{username}_{i}"
                                    i += 1
                                username = temp_username
                                
                                user = User.objects.create_user(
                                    username=username,
                                    email=email,
                                    is_active=True
                                )
                                # Set Cloudflare info for new user
                                user.profile.cloudflare_id = cloudflare_id
                                user.profile.is_cloudflare_user = True
                                user.profile.cloudflare_email = email
                                user.profile.save()
                                logger.info(f"Created new user for Cloudflare user: {email}")
                        
                        # Update last login time
                        user.profile.last_cloudflare_login = timezone.now()
                        user.profile.save()
                        
                        # Log the user in
                        login(request, user)
                        logger.info(f"Auto-logged in Cloudflare user: {email}")
                        
                        # Redirect from login page if that's where we were headed
                        if request.path == reverse('login'):
                            logger.info(f"Redirecting Cloudflare user from login page to home")
                            return HttpResponseRedirect('/')
                    except Exception as e:
                        logger.error(f"Error auto-provisioning user from Cloudflare: {str(e)}")
        
        # Process the request and return the response
        return self.get_response(request)