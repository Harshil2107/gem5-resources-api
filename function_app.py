import azure.functions as func
import json
import logging
import pymongo
import os
from bson import json_util
from urllib.parse import parse_qs

app = func.FunctionApp()

# Load MongoDB connection string from environment variables
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING", "mongodb://localhost:27017")

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_CONNECTION_STRING)
db = client["gem5-vision"]
collection = db["resources"]


def create_error_response(status_code: int, message: str) -> func.HttpResponse:
    """Create an error response with appropriate headers."""
    return func.HttpResponse(
        body=json.dumps({"error": message}),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )


@app.route(route="resources/{resource_id}")
def get_resource_by_id(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get a resource by ID with optional version filter.

    Route: /resources/{resource_id}

    Query Parameters:
    - resource_version: Optional. If provided, returns only the resource with matching ID and version.
    """

    logging.info('Processing request to get resource by ID')
    try:
        # Get the resource ID from the route parameter
        resource_id = req.route_params.get('resource_id')
        if not resource_id:
            return create_error_response(400, "Resource ID is required")

        # Get optional resource version from query parameters
        resource_version = req.params.get('resource_version')

        # Create query
        query = {"id": resource_id}
        if resource_version:
            query["resource_version"] = resource_version

        resource = list(collection.find(query, {"_id": 0}))

        if not resource:
            return create_error_response(404, f"Resource with ID '{resource_id}' not found")

        return func.HttpResponse(
            body=json.dumps(resource, default=json_util.default),
            headers={"Content-Type": "application/json"},
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error fetching resource by ID: {str(e)}")
        return create_error_response(500, "Internal server error")

@app.route(route="resources/search-by-ids")
def get_resources_by_batch(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get multiple resources by their IDs and versions.

    Route: /resources/search-by-ids

    Query Parameters:
    - id: Required, can appear multiple times (up to 40)
    - version: Required, must match number of id parameters and be in same order
    """
    logging.info('Processing request to get resources by batch')
    try:
        query_params = parse_qs(req.url.split('?', 1)[1] if '?' in req.url else '')
        ids = query_params.get('id', [])
        versions = query_params.get('version', [])

        # Validate inputs
        if not ids or not versions:
            return create_error_response(400, "Both 'id' and 'version' parameters are required")

        if len(ids) != len(versions):
            return create_error_response(400, "Number of 'id' parameters must match number of 'version' parameters")

        # Create a list of queries for MongoDB $or operator
        queries = [{"id": id, "resource_version": version} for id, version in zip(ids, versions)]

        resources = list(collection.find({"$or": queries}, {"_id": 0}))

        # Check if all requested resources were found
        if len(resources) != len(ids):
            # Could be more specific about which resources were not found
            return create_error_response(404, "One or more requested resources were not found")

        return func.HttpResponse(
            body=json.dumps(resources),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )

    except Exception as e:
        logging.error(f"Error fetching resources by batch: {str(e)}")
        return create_error_response(500, "Internal server error")