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

@app.function_name(name="get_resource_by_id")
@app.route(route="resources/find-resource-by-id", auth_level=func.AuthLevel.FUNCTION)
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
        resource_id = req.params.get('id')
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

@app.function_name(name="get_resources_by_batch")
@app.route(route="resources/find-resources-in-batch", auth_level=func.AuthLevel.FUNCTION)
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
        versions = query_params.get('resource_version', [])

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

@app.function_name(name="search_resources")   
@app.route(route="resources/search", auth_level=func.AuthLevel.FUNCTION)
def search_resources(req: func.HttpRequest) -> func.HttpResponse:
    """
    Search resources with filtering capabilities.

    Route: /resources/search

    Query Parameters:
    - contains-str: Optional. The search term to find resources.
    - must-include: Optional. A CSV-formatted string defining filter criteria.
    - sort: Optional. Sort criteria ('date', 'name', 'version', 'id_asc', 'id_desc'). Default is score-based.
    - page: Optional. Page number for pagination (default: 1).
    - page-size: Optional. Number of results per page (default: 10).
    """
    logging.info('Processing request to search resources')
    try:
        # Get search query
        contains_str = req.params.get('contains-str', "").strip()
        
        # Get optional filter criteria
        must_include = req.params.get('must-include')
        
        # Get sort parameter
        sort_param = req.params.get('sort')
        
        # Get pagination parameters
        try:
            page = int(req.params.get('page', 1))
            page_size = int(req.params.get('page-size', 10))
        except ValueError:
            return create_error_response(400, "Invalid pagination parameters")

        # Create query object similar to the one used in the Data API
        query_object = {
            "query": contains_str,
            "sort": sort_param if sort_param else "default"
        }
        
        # Parse filter criteria similar to MongoDB implementation
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
                    
                    # Add to query object similar to original implementation
                    query_object[field] = values
            except Exception as e:
                logging.error(f"Error parsing filter criteria: {str(e)}")
                return create_error_response(400, "Invalid filter format")

        # Build the aggregation pipeline
        pipeline = []
        
        # Add search query stage if a query is provided
        if contains_str:
            pipeline.extend(get_search_pipeline(query_object))
        
        # Add filter pipeline stages
        pipeline.extend(get_filter_pipeline(query_object))
        
        # Add latest version pipeline
        pipeline.extend(get_latest_version_pipeline())
        
        # Add sort pipeline
        pipeline.extend(get_sort_pipeline(query_object))
        
        # Add pagination
        pipeline.extend(get_page_pipeline(page, page_size))
        
        # Execute the aggregation
        results = list(collection.aggregate(pipeline))
        
        # Process results to match expected output format
        processed_results = []
        total_count = 0
        
        if results:
            processed_results = results
            total_count = results[0].get('totalCount', 0) if results else 0
            
            # Remove MongoDB _id field and ensure database field is added
            for resource in processed_results:
                if '_id' in resource:
                    del resource['_id']
                resource['database'] = "gem5-vision"  # Add database field like in original implementation
        
        response_data = {
            "documents": processed_results,
            "totalCount": total_count
        }
        
        return func.HttpResponse(
            body=json.dumps(response_data, default=json_util.default),
            headers={"Content-Type": "application/json"},
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error searching resources: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")

# Helper functions from original implementation

def get_sort(sort):
    """Return sort object based on sort parameter."""
    switch_dict = {
        "date": {"date": -1},
        "name": {"id": 1},
        "version": {"ver_latest": -1},
        "id_asc": {"id": 1},
        "id_desc": {"id": -1}
    }
    return switch_dict.get(sort, {"score": -1})

def get_latest_version_pipeline():
    """Return pipeline to get latest version of each resource."""
    return [
        {
            "$addFields": {
                "resource_version_parts": {
                    "$map": {
                        "input": {
                            "$split": ["$resource_version", "."],
                        },
                        "as": "item",
                        "in": {"$toInt": "$$item"},
                    },
                },
            },
        },
        {
            "$sort": {
                "id": 1,
                "resource_version_parts.0": -1,
                "resource_version_parts.1": -1,
                "resource_version_parts.2": -1,
                "resource_version_parts.3": -1,
            },
        },
        {
            "$group": {
                "_id": "$id",
                "latest_version": {
                    "$first": "$resource_version",
                },
                "document": {"$first": "$$ROOT"},
            },
        },
        {
            "$replaceRoot": {
                "newRoot": {
                    "$mergeObjects": [
                        "$document",
                        {
                            "id": "$_id",
                            "latest_version": "$latest_version",
                        },
                    ],
                },
            },
        },
    ]

def get_search_pipeline(query_object):
    """Return pipeline for text search."""
    
    pipeline = [
        {
            "$search": {
                "compound": {
                    "should": [
                        {
                            "text": {
                                "path": "id",
                                "query": query_object["query"],
                                "score": {
                                    "boost": {
                                        "value": 10
                                    }
                                }
                            }
                        },
                        {
                            "text": {
                                "path": "gem5_versions",
                                "query": "24.1",
                                "score": {
                                    "boost": {
                                        "value": 10
                                    }
                                }
                            }
                        }
                    ],
                    "must": [
                        {
                            "text": {
                                "query": query_object["query"],
                                "path": [
                                    "id",
                                    "desciption",
                                    "category",
                                    "architecture",
                                    "tags"
                                ],
                                "fuzzy": {
                                    "maxEdits": 2,
                                    "maxExpansions": 100
                                }
                            }
                        }
                    ]
                }
            }
        },
        {
            "$addFields": {
                "score": {
                    "$meta": "searchScore"
                }
            }
        }
    ]

    return pipeline

def get_filter_pipeline(query_object):
    """Return pipeline to apply filters."""
    pipeline = []
    
    # Filter by tags
    if query_object.get("tags"):
        pipeline.extend([
            {
                "$addFields": {
                    "tag": "$tags",
                },
            },
            {
                "$unwind": "$tag",
            },
            {
                "$match": {
                    "tag": {
                        "$in": query_object["tags"],
                    },
                },
            },
            {
                "$group": {
                    "_id": "$_id",
                    "doc": {
                        "$first": "$$ROOT",
                    },
                },
            },
            {
                "$replaceRoot": {
                    "newRoot": "$doc",
                },
            },
        ])
    
    # Filter by gem5_versions
    if query_object.get("gem5_versions"):
        pipeline.extend([
            {
                "$addFields": {
                    "version": "$gem5_versions",
                },
            },
            {
                "$unwind": "$version",
            },
            {
                "$match": {
                    "version": {
                        "$in": query_object["gem5_versions"],
                    },
                },
            },
            {
                "$group": {
                    "_id": "$_id",
                    "doc": {
                        "$first": "$$ROOT",
                    },
                },
            },
            {
                "$replaceRoot": {
                    "newRoot": "$doc",
                },
            },
        ])
    
    # Add other filters (category and architecture)
    match_conditions = []
    if query_object.get("category"):
        match_conditions.append({"category": {"$in": query_object["category"]}})
    
    if query_object.get("architecture"):
        match_conditions.append({"architecture": {"$in": query_object["architecture"]}})
    
    if match_conditions:
        pipeline.append({
            "$match": {
                "$and": match_conditions
            }
        })
    
    return pipeline

def get_sort_pipeline(query_object):
    """Return pipeline to apply sorting."""
    return [
        {
            "$addFields": {
                "ver_latest": {
                    "$max": {"$ifNull": ["$gem5_versions", []]},
                },
            },
        },
        {
            "$sort": get_sort(query_object.get("sort")),
        }
    ]

def get_page_pipeline(current_page, page_size):
    """Return pipeline to apply pagination."""
    return [
        {
            "$group": {
                "_id": None,
                "totalCount": {"$sum": 1},
                "items": {"$push": "$$ROOT"}
            }
        },
        {
            "$unwind": "$items"
        },
        {
            "$replaceRoot": {"newRoot": {
                "$mergeObjects": ["$items", {"totalCount": "$totalCount"}]
            }}
        },
        {
            "$skip": (current_page - 1) * page_size,
        },
        {
            "$limit": page_size,
        }
    ]
    
    

@app.route(route="resources/filters", auth_level=func.AuthLevel.FUNCTION)
def get_filters(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get distinct categories, architectures, and gem5 versions from the resources collection.

    Route: /resources/filters

    No query parameters required for this endpoint.
    """
    logging.info('Processing request to get resource filters')
    try:
        # Build the aggregation pipeline to get distinct values
        pipeline = [
            {
                "$unwind": {
                    "path": "$gem5_versions",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$group": {
                    "_id": None,
                    "category": {"$addToSet": "$category"},
                    "architecture": {"$addToSet": "$architecture"},
                    "gem5_versions": {"$addToSet": "$gem5_versions"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "category": 1,
                    "architecture": 1,
                    "gem5_versions": 1
                }
            }
        ]
        
        # Execute the aggregation
        results = list(collection.aggregate(pipeline))
        
        # If no results, return empty arrays
        if not results:
            return func.HttpResponse(
                body=json.dumps({
                    "category": [],
                    "architecture": [],
                    "gem5_versions": []
                }),
                headers={"Content-Type": "application/json"},
                status_code=200
            )
        
        # Process the results
        filters = results[0]
        
        # Filter out null values from architecture
        if "architecture" in filters:
            filters["architecture"] = [a for a in filters["architecture"] if a is not None]
        
        # Sort the arrays
        if "category" in filters:
            filters["category"].sort()
        if "architecture" in filters:
            filters["architecture"].sort()
        if "gem5_versions" in filters:
            filters["gem5_versions"].sort(reverse=True)
        
        return func.HttpResponse(
            body=json.dumps(filters, default=json_util.default),
            headers={"Content-Type": "application/json"},
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error getting resource filters: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")
    
@app.route(route="resources/get-dependent-workloads", auth_level=func.AuthLevel.FUNCTION)
def get_dependent_workloads(req: func.HttpRequest) -> func.HttpResponse:
    """
    Find workloads that depend on a specified resource ID.

    Route: /resources/dependent-workloads

    Query Parameters:
    - id: Required. The resource ID to find dependent workloads for.
    
    Returns:
    - A list of workload that depend on the specified resource.
    """
    logging.info('Processing request to find dependent workloads')
    
    try:
        # Get required resource ID parameter
        resource_id = req.params.get('id')
        if not resource_id:
            return create_error_response(400, "Missing required parameter 'id'")
        
        # Build pipeline to find dependent workloads
        pipeline = [
            {
                "$match": {
                    "category": "workload"
                }
            },
            {
                "$addFields": {
                    "resources": {
                        "$objectToArray": "$resources"
                    }
                }
            },
            {
                "$unwind": "$resources"
            },
            {
                "$match": {
                    "resources.v": resource_id
                }
            },
            {
                "$group": {
                    "_id": "$id",
                }
            }
        ]
        
        # Execute the pipeline
        workloads = list(collection.aggregate(pipeline))
        
        return func.HttpResponse(
            body=json.dumps(workloads),
            headers={"Content-Type": "application/json"},
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Error finding dependent workloads: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")