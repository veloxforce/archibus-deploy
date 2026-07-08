"""Bruce BEM API client with dual authentication modes.

Production: Rain token from Bruce BEM iframe (X-Rain-User-Token header required)
Staging: Username/password login via .env credentials (STAGING_MODE=true)

Auth Flow:
    Production: Rain token → use as user_token + OAuth bearer_token
    Staging: POST /users/getusertoken with USERNAME/PASSWORD → user_token + OAuth bearer_token

Design Context:
    STAGING_MODE enables testing without Bruce BEM iframe integration.
    Mohamed can access staging LibreChat directly, MCP authenticates via .env credentials.
    See issue #602 for ship-with-confidence staging architecture.
"""
import os
import logging
import requests
from typing import Optional
from fastmcp import Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers

logger = logging.getLogger(__name__)

# Off by default. Set RAIN_DEBUG=1 to emit credential-adjacent diagnostics
# (OAUTH_CLIENT_ID prefix, Rain token prefix, refresh token prefix).
# Prevents credential leakage through docker logs in production deployments.
RAIN_DEBUG = os.getenv("RAIN_DEBUG") == "1"


class Settings:
    """Configuration settings for Bruce BEM API integration"""

    def __init__(self):
        # Use direct os.getenv() like in our working test_api.py
        self.USER_AUTH_URL = os.getenv("USER_AUTH_URL")
        self.BEM_API_URL = os.getenv("BEM_API_URL")
        self.USER_API_CLIENT_ID = os.getenv("USER_API_CLIENT_ID")
        self.OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
        self.CLIENT_SECRET = os.getenv("CLIENT_SECRET")
        self.USERNAME = os.getenv("USERNAME")
        self.PASSWORD = os.getenv("PASSWORD")
        self.OAUTH_URL = os.getenv("OAUTH_URL")
        self.AUDIENCE = os.getenv("AUDIENCE")
        self.GRANT_TYPE = os.getenv("GRANT_TYPE", "client_credentials")
        # Staging mode: bypass Rain token, use USERNAME/PASSWORD for auth
        self.STAGING_MODE = os.getenv("STAGING_MODE", "false").lower() == "true"

        # Debug log environment variables (OAUTH_CLIENT_ID prefix gated behind RAIN_DEBUG)
        if RAIN_DEBUG:
            logger.debug(f"Environment variables loaded:")
            logger.debug(f"  USER_AUTH_URL: {self.USER_AUTH_URL}")
            logger.debug(f"  BEM_API_URL: {self.BEM_API_URL}")
            logger.debug(f"  OAUTH_URL: {self.OAUTH_URL}")
            logger.debug(
                f"  OAUTH_CLIENT_ID: {self.OAUTH_CLIENT_ID[:10]}..."
                if self.OAUTH_CLIENT_ID
                else "None"
            )
            logger.debug(f"  AUDIENCE: {self.AUDIENCE}")


class AuthPersistenceMiddleware(Middleware):
    """Middleware that handles authentication persistence using FastMCP Context state management"""

    def __init__(self, client: 'BruceBEMClient'):
        self.client = client

    async def on_request(self, context: MiddlewareContext, call_next):
        """Ensure authentication tokens are available for all requests.

        Authentication strategy (production):
        1. Rain token REQUIRED in headers → use as user_token (error if missing)
        2. Bearer token obtained via OAuth client_credentials (hardcoded service account)

        Authentication strategy (staging - STAGING_MODE=true):
        1. No Rain token required
        2. User token obtained via /users/getusertoken with USERNAME/PASSWORD from .env
        3. Bearer token obtained via OAuth client_credentials
        """
        # STAGING_MODE: Bypass Rain token, use .env credentials
        if self.client.settings.STAGING_MODE:
            logger.info("[BRUCE_BEM] STAGING_MODE active - using .env credentials")
            try:
                auth_result = self.client.authenticate_with_credentials()
                if context.fastmcp_context:
                    token_data = {
                        "user_token": self.client.user_token,
                        "bearer_token": self.client.bearer_token,
                        "staging_mode": True,
                        "auth_result": auth_result
                    }
                    context.fastmcp_context.set_state("auth_tokens", token_data)
                return await call_next(context)
            except Exception as e:
                logger.error(f"[BRUCE_BEM] Staging auth failed: {e}")
                raise ValueError(f"Staging authentication failed: {e}")

        # Production mode: Extract Rain tokens from HTTP headers
        headers = get_http_headers()
        rain_user_token = headers.get('x-rain-user-token')
        rain_refresh_token = headers.get('x-rain-refresh-token')

        # Guard clause: Rain token is REQUIRED in production
        if not rain_user_token:
            logger.error("[BRUCE_BEM] Missing X-Rain-User-Token header - authentication rejected")
            raise ValueError("Rain user token required. Ensure request comes from Bruce BEM iframe with valid userToken.")

        if RAIN_DEBUG:
            logger.debug(f"[BRUCE_BEM] Using Rain user token: {rain_user_token[:20]}...")
            if rain_refresh_token:
                logger.debug(f"[BRUCE_BEM] Refresh token available: {rain_refresh_token[:20]}...")

        # Guard clause: Skip if no FastMCP context available
        if not context.fastmcp_context:
            return await call_next(context)

        # Guard clause: Use cached tokens if Rain token unchanged
        cached_tokens = context.fastmcp_context.get_state("auth_tokens")
        if cached_tokens and cached_tokens.get("rain_user_token") == rain_user_token:
            self.client.user_token = cached_tokens.get("user_token")
            self.client.bearer_token = cached_tokens.get("bearer_token")
            logger.debug("[BRUCE_BEM] Using cached tokens")
            return await call_next(context)

        # Cache miss: no cache OR different Rain token (different user)
        if cached_tokens:
            logger.info("[BRUCE_BEM] Rain token changed - refreshing authentication")

        # Authenticate: pass Rain token if present
        try:
            auth_result = self.client.authenticate(rain_user_token=rain_user_token)
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            return await call_next(context)

        # Guard clause: Only cache if authentication succeeded
        if not (auth_result.get("user_token") and self.client.user_token):
            return await call_next(context)

        # Cache tokens with Rain tokens for invalidation and refresh
        token_data = {
            "user_token": self.client.user_token,
            "bearer_token": self.client.bearer_token,
            "rain_user_token": rain_user_token,
            "rain_refresh_token": rain_refresh_token,
            "auth_result": auth_result
        }
        context.fastmcp_context.set_state("auth_tokens", token_data)
        logger.debug("Authentication tokens cached in context state")

        return await call_next(context)


class BruceBEMClient:
    """Client for Bruce BEM API operations"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.user_token = None
        self.bearer_token = None

    def authenticate(self, ctx: Optional[Context] = None, rain_user_token: Optional[str] = None) -> dict:
        """Authenticate with Bruce BEM system and obtain required tokens.

        Args:
            ctx: FastMCP context for cached token retrieval
            rain_user_token: REQUIRED. Pre-authenticated user token from Rain (Bruce BEM iframe).
        """
        # Guard clause: Check context state first for cached tokens
        if ctx:
            cached_tokens = ctx.get_state("auth_tokens")
            if cached_tokens:
                self.user_token = cached_tokens.get("user_token")
                self.bearer_token = cached_tokens.get("bearer_token")
                logger.debug("Using cached authentication tokens from context")
                return cached_tokens.get("auth_result", {
                    "user_token": True,
                    "bearer_token": True,
                    "errors": [],
                    "message": "Using cached authentication"
                })

        # Guard clause: Rain token is required
        if not rain_user_token:
            raise ValueError("Rain user token required - no fallback to env credentials")

        results = {"user_token": False, "bearer_token": False, "errors": []}

        # Use Rain token as user_token
        self.user_token = rain_user_token
        results["user_token"] = True
        logger.info("[BRUCE_BEM] Using Rain token as user_token")

        # Get Bearer Token
        try:
            payload = {
                "client_id": self.settings.OAUTH_CLIENT_ID,
                "client_secret": self.settings.CLIENT_SECRET,
                "grant_type": self.settings.GRANT_TYPE,
                "audience": self.settings.AUDIENCE,
            }

            # Debug logging
            logger.debug(f"OAuth URL: {self.settings.OAUTH_URL}")
            logger.debug(f"OAuth payload: {payload}")

            response = requests.post(self.settings.OAUTH_URL, json=payload)
            logger.debug(f"OAuth response status: {response.status_code}")
            logger.debug(f"OAuth response text: {response.text}")

            if response.status_code == 200:
                data = response.json()
                self.bearer_token = data.get("access_token")
                results["bearer_token"] = True
            else:
                results["errors"].append(
                    f"Bearer Token failed: {response.status_code} - {response.text}"
                )

        except Exception as e:
            results["errors"].append(f"Bearer Token error: {str(e)}")

        return results

    def authenticate_with_credentials(self) -> dict:
        """Authenticate using .env credentials (STAGING_MODE).

        Calls /users/getusertoken with USERNAME/PASSWORD to obtain user_token,
        then gets bearer_token via OAuth client_credentials flow.

        Returns:
            Dict with user_token, bearer_token success flags and any errors
        """
        results = {"user_token": False, "bearer_token": False, "errors": []}

        # Get user token via username/password
        try:
            url = f"{self.settings.USER_AUTH_URL}users/getusertoken"
            payload = {
                "username": self.settings.USERNAME,
                "password": self.settings.PASSWORD,
                "clientId": self.settings.USER_API_CLIENT_ID,
            }

            logger.debug(f"[STAGING] Authenticating with credentials at {url}")
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                self.user_token = data.get("accessToken")
                if self.user_token:
                    results["user_token"] = True
                    logger.info("[STAGING] User token obtained via credentials")
                else:
                    results["errors"].append("Response missing accessToken")
            else:
                results["errors"].append(
                    f"User token failed: {response.status_code} - {response.text}"
                )
        except Exception as e:
            results["errors"].append(f"User token error: {str(e)}")

        # Get Bearer Token (same as production)
        try:
            payload = {
                "client_id": self.settings.OAUTH_CLIENT_ID,
                "client_secret": self.settings.CLIENT_SECRET,
                "grant_type": self.settings.GRANT_TYPE,
                "audience": self.settings.AUDIENCE,
            }

            response = requests.post(self.settings.OAUTH_URL, json=payload)
            if response.status_code == 200:
                data = response.json()
                self.bearer_token = data.get("access_token")
                results["bearer_token"] = True
                logger.info("[STAGING] Bearer token obtained")
            else:
                results["errors"].append(
                    f"Bearer Token failed: {response.status_code} - {response.text}"
                )
        except Exception as e:
            results["errors"].append(f"Bearer Token error: {str(e)}")

        return results

    def refresh_user_token(self, refresh_token: str) -> str:
        """Refresh the user token using the refresh token.

        Args:
            refresh_token: The Rain refresh token from Bruce BEM

        Returns:
            New access token string

        Raises:
            ValueError: If refresh fails
        """
        # Note: refresh endpoint is on USER_AUTH_URL, not BEM_API_URL
        url = f"{self.settings.USER_AUTH_URL}users/refreshtoken"
        payload = {
            "refreshtoken": refresh_token,
            "clientId": self.settings.USER_API_CLIENT_ID,
        }
        # API requires x-user-token header even for refresh (uses old token for identification)
        headers = {"Content-Type": "application/json", "x-user-token": self.user_token or ""}

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("accessToken")
                if new_token:
                    self.user_token = new_token
                    logger.info("[BRUCE_BEM] Token refreshed successfully")
                    return new_token
                raise ValueError("Refresh response missing accessToken")
            raise ValueError(f"Token refresh failed: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            raise ValueError(f"Token refresh error: {str(e)}")

    def _make_api_request(self, url: str, payload: dict, ctx: Optional[Context] = None) -> requests.Response:
        """Make API request with automatic 401 retry using refresh token.

        Args:
            url: API endpoint URL
            payload: Request payload
            ctx: FastMCP context for accessing cached refresh token

        Returns:
            Response object

        Raises:
            ValueError: If request fails after refresh attempt
        """
        headers = {"Content-Type": "application/json", "x-user-token": self.user_token}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        response = requests.post(url, json=payload, headers=headers)

        # If 401, try to refresh token and retry once
        if response.status_code == 401 and ctx:
            cached_tokens = ctx.get_state("auth_tokens")
            refresh_token = cached_tokens.get("rain_refresh_token") if cached_tokens else None

            if not refresh_token:
                raise ValueError("Token expired and no refresh token available")

            logger.info("[BRUCE_BEM] Got 401 - attempting token refresh")
            try:
                new_token = self.refresh_user_token(refresh_token)
                headers["x-user-token"] = new_token

                # Update cache with new token
                if cached_tokens:
                    cached_tokens["user_token"] = new_token
                    ctx.set_state("auth_tokens", cached_tokens)

                # Retry request
                response = requests.post(url, json=payload, headers=headers)
                logger.info(f"[BRUCE_BEM] Retry after refresh: {response.status_code}")
            except ValueError as e:
                raise ValueError(f"Token refresh failed: {e}")

        return response

    def search_assets(
        self,
        name: Optional[str] = None,
        asset_type: Optional[str] = None,
        location: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> list:
        """Search for assets in Bruce BEM system using flexible parameters. Always includes work request data to populate assetMainType."""
        # Guard clause: Try to use cached authentication if available
        if not self.user_token and ctx:
            cached_tokens = ctx.get_state("auth_tokens")
            if cached_tokens:
                self.user_token = cached_tokens.get("user_token")
                self.bearer_token = cached_tokens.get("bearer_token")

        # Guard clause: Authentication still required
        if not self.user_token:
            raise ValueError(
                "Authentication required. Call authenticate_bruce_bem() first."
            )

        # Validate that at least one parameter is provided (API constraint)
        has_name = name and len(name.strip()) > 0
        has_asset_type = asset_type and len(asset_type.strip()) > 0
        has_location = location and len(location.strip()) > 0

        if not (has_name or has_asset_type or has_location):
            raise ValueError(
                "At least one search parameter (name, asset_type, or location) must be provided"
            )

        url = f"{self.settings.BEM_API_URL}assets/GetAssetsByName"
        payload = {
            "name": name if has_name else None,
            "assettype": asset_type if has_asset_type else None,
            "location": location if has_location else None,
            "IncludeWorkRequests": 1,
        }

        try:
            response = self._make_api_request(url, payload, ctx)
            if response.status_code == 200:
                return response.json().get("collection", [])
            raise ValueError(f"Asset search failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise ValueError(f"Asset search error: {str(e)}")

    def create_work_request(self, asset_id: str, short_description: str, problem_details: str, status, ctx: Optional[Context] = None) -> str:
        """Create work request for an asset"""
        # Guard clause: Try to use cached authentication if available
        if not self.user_token and ctx:
            cached_tokens = ctx.get_state("auth_tokens")
            if cached_tokens:
                self.user_token = cached_tokens.get("user_token")
                self.bearer_token = cached_tokens.get("bearer_token")

        # Guard clause: Authentication still required
        if not self.user_token:
            raise ValueError(
                "Authentication required. Call authenticate_bruce_bem() first."
            )

        url = f"{self.settings.BEM_API_URL}workrequest/CreateWorkRequest"
        payload = {
            "shortDescription": short_description,
            "problem": problem_details,
            "dueDate": None,
            "assetId": asset_id,
            "providerMemberId": None,
            "status": status.value,
        }

        try:
            response = self._make_api_request(url, payload, ctx)
            if response.status_code == 200:
                return response.text.strip('"')
            raise ValueError(f"Work request creation failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise ValueError(f"Work request creation error: {str(e)}")