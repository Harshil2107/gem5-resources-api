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


@app.route(route="resources/find-resource-by-id")
def get_resource_by_id(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get a resource by ID with optional version filter.

    Route: /resources/{resource_id}

    Query Parameters:
    - resource_id: Required. The id of the resource to find.
    - resource_version: Optional. If provided, returns only the resource with matching ID and version.
    """

    logging.info('Processing request to get resource by ID')
    try:
        # Get the resource ID from the route parameter
        resource_id = req.params.get('resource_id')
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

@app.route(route="resources/find-resources-in-batch")
def get_resources_by_batch(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get multiple resources by their IDs and versions.

    Route: /resources/find-resources-in-batch

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
    
@app.route(route="resources/search")
def search_resources(req: func.HttpRequest) -> func.HttpResponse:
    """
    Search resources with filtering capabilities.

    Route: /resources/search

    Query Parameters:
    - contains-str: Required. The search term to find resources.
    - must-include: Optional. A CSV-formatted string defining filter criteria.
    - page: Optional. Page number for pagination (default: 1).
    - page-size: Optional. Number of results per page (default: 10).
    """
    logging.info('Processing request to search resources')
    try:
        # Get required search term
        contains_str = req.params.get('contains-str')
        if not contains_str:
            return create_error_response(400, "Search term (contains-str) is required")

        # Get optional filter criteria
        must_include = req.params.get('must-include')
        
        # Get pagination parameters
        try:
            page = int(req.params.get('page', 1))
            page_size = int(req.params.get('page-size', 10))
        except ValueError:
            return create_error_response(400, "Invalid pagination parameters")

        # Parse filter criteria
        filter_criteria = {}
        if must_include:
            try:
                # Parse must-include parameter format: field1,value1,value2;field2,value1,value2
                for group in must_include.split(';'):
                    if not group:
                        continue
                    parts = group.split(',')
                    if len(parts) < 2:
                        return create_error_response(400, "Invalid filter format")
                    
                    field = parts[0]
                    values = parts[1:]
                    
                    # Handle special case for gem5_versions which is an array field
                    if field == "gem5_versions":
                        filter_criteria[field] = {"$in": values}
                    else:
                        filter_criteria[field] = {"$in": values}
            except Exception as e:
                logging.error(f"Error parsing filter criteria: {str(e)}")
                return create_error_response(400, "Invalid filter format")

        # Build the aggregation pipeline using concepts from the provided MongoDB code
        pipeline = []
        
        # First stage: Text search
        pipeline.append({
            "$match": {
                "$or": [
                    {"id": {"$regex": contains_str, "$options": "i"}},
                    {"description": {"$regex": contains_str, "$options": "i"}},
                    {"category": {"$regex": contains_str, "$options": "i"}},
                    {"architecture": {"$regex": contains_str, "$options": "i"}},
                    {"tags": {"$regex": contains_str, "$options": "i"}}
                ]
            }
        })
        
        # Add filter criteria if present
        if filter_criteria:
            pipeline.append({"$match": filter_criteria})
        
        # Get latest version for each resource if no specific version is requested
        # This mimics the behavior of getLatestVersionPipeline from the provided code
        resource_versions_requested = filter_criteria.get("resource_version", {}).get("$in", []) if filter_criteria.get("resource_version") else []
        
        if not resource_versions_requested:
            # Sort by version components
            pipeline.append({
                "$addFields": {
                    "version_parts": {
                        "$map": {
                            "input": {"$split": ["$resource_version", "."]},
                            "as": "part",
                            "in": {"$toInt": "$$part"}
                        }
                    }
                }
            })
            
            pipeline.append({
                "$sort": {
                    "id": 1,
                    "version_parts.0": -1,
                    "version_parts.1": -1,
                    "version_parts.2": -1
                }
            })
            
            pipeline.append({
                "$group": {
                    "_id": "$id",
                    "doc": {"$first": "$$ROOT"}
                }
            })
            
            pipeline.append({
                "$replaceRoot": {"newRoot": "$doc"}
            })
        
        # Apply pagination
        pipeline.append({"$skip": (page - 1) * page_size})
        pipeline.append({"$limit": page_size})
        
        # Hide MongoDB _id field
        pipeline.append({"$project": {"_id": 0}})
        
        # Execute the aggregation
        results = list(collection.aggregate(pipeline))
        
        return func.HttpResponse(
            body=json.dumps(results, default=json_util.default),
            headers={"Content-Type": "application/json"},
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error searching resources: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")