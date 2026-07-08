import logging
from typing import Annotated
from fastmcp import FastMCP, Context
from pydantic import Field

# Import our refactored modules
from src.utils import clean_null_values
from src.api import Settings, BruceBEMClient, AuthPersistenceMiddleware
from src.types import AssetType, WorkRequestStatus

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment variables from .env file")
except ImportError:
    logger.warning("python-dotenv not available, using system environment variables")

# Initialize FastMCP server
settings = Settings()
client = BruceBEMClient(settings)
mcp = FastMCP("bruce-bem-tools")

# Add authentication persistence middleware
auth_middleware = AuthPersistenceMiddleware(client)
mcp.add_middleware(auth_middleware)


@mcp.tool
def authenticate_bruce_bem(ctx: Context) -> dict:
    """
    Authenticate with Bruce BEM facility management system.

    Obtains required UserToken and Bearer Token for API access.
    Authentication tokens are automatically cached for subsequent requests.

    Returns status confirmation with authentication results.
    """
    try:
        result = client.authenticate(ctx)

        if result.get("user_token") and result.get("bearer_token"):
            return {
                "status": "success",
                "data": {
                    "authenticated": True,
                    "user_token": bool(result.get("user_token")),
                    "bearer_token": bool(result.get("bearer_token"))
                },
                "error": None
            }
        else:
            return {
                "status": "error",
                "data": None,
                "error": f"Authentication failed: {', '.join(result.get('errors', []))}"
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "error": f"Authentication error: {str(e)}"
        }


@mcp.tool
def search_assets(
    ctx: Context,
    name: Annotated[
        str,
        Field(description="Search words (each searched in name/details fields)"),
    ] = "",
    asset_type: Annotated[
        AssetType,
        Field(description="Equipment type from AssetType enum"),
    ] = AssetType.UNSPECIFIED,
    location: Annotated[
        str,
        Field(description="City, district, street address, or area"),
    ] = "",
) -> dict:
    """
    Search for assets in the Bruce BEM facility management system.

    **Parameters**
    - Location: City, district, street address, or area

    Always includes work request data to populate assetMainType field and provide cost estimates.
    """
    try:
        # Clean up parameters - convert empty strings to None
        clean_name = name.strip() if name and name.strip() else None
        clean_asset_type = (
            asset_type.value if asset_type != AssetType.UNSPECIFIED else None
        )
        clean_location = location.strip() if location and location.strip() else None

        results = client.search_assets(clean_name, clean_asset_type, clean_location, ctx)

        # Apply null value filtering to results
        cleaned_results = clean_null_values(results)

        return {
            "status": "success",
            "data": cleaned_results,
            "error": None
        }

    except ValueError as e:
        return {
            "status": "error",
            "data": None,
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "error": f"Search error: {str(e)}"
        }


@mcp.tool
def create_work_request(
    ctx: Context,
    asset_id: Annotated[
        str,
        Field(description="Unique asset identifier"),
    ],
    short_description: Annotated[
        str,
        Field(description="Brief problem statement (e.g., 'Elevator not working')"),
    ],
    problem_details: Annotated[
        str,
        Field(description="Complete description with context and details"),
    ],
    status: Annotated[
        WorkRequestStatus,
        Field(description="Work request status"),
    ] = WorkRequestStatus.REQUESTED,
) -> dict:
    """
    Create a maintenance work request for a specific asset.
    """
    try:
        work_request_result = client.create_work_request(asset_id, short_description, problem_details, status, ctx)

        return {
            "status": "success",
            "data": {
                "work_request_id": work_request_result,
                "asset_id": asset_id,
                "short_description": short_description,
                "problem_details": problem_details
            },
            "error": None
        }

    except ValueError as e:
        return {
            "status": "error",
            "data": None,
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "error": f"Work request creation error: {str(e)}"
        }


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)