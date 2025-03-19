# Azure Function with MongoDB Integration

## Overview

This document provides step-by-step instructions for setting up, running, and testing an Azure Function that queries a MongoDB database.

## Prerequisites

Ensure the following dependencies and tools are installed before proceeding:

### Required Software

- **Python 3.10 or 3.11** (Azure Functions does not support Python 3.12 yet)

- **Azure Functions Core Tools**

  ```bash
  npm install -g azure-functions-core-tools@4 --unsafe-perm true
  ```

### Required Python Packages

These dependencies must be installed inside a virtual environment:

```bash
pip install azure-functions pymongo requests
```

## Running the Azure Function

### 1**Activate the Virtual Environment**

```bash
cd AzureFunctionsDemo
source venv/bin/activate  # On Windows, use venv\Scripts\activate
```

### 2️ **Set Environment Variables**

Ensure the `local.settings.json` file contains the correct MongoDB connection string:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "MONGO_CONNECTION_STRING": "mongodb+srv://username:password@cluster0.mongodb.net/myDatabase?retryWrites=true&w=majority",
    "FUNCTIONS_WORKER_RUNTIME": "python"
  }
}
```

### 3️ **Run the Azure Function Locally**

```bash
func start
```

Expected output:

```bash
Functions:

        get_resources_by_batch:  http://localhost:7071/api/resources/search-by-ids

        get_resource_by_id:  http://localhost:7071/api/resources/{resource_id}
```

## Testing the Function

### **Using Python Script**

Run the test script, make sure Azure functions is running locally:

```bash
python3 -m unittest resources_api_tests.py -v
```
