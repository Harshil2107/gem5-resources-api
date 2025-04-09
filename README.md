# Azure Function with MongoDB Integration

## Overview

This document provides step-by-step instructions for setting up, running, and testing an Azure Function that queries a MongoDB database.

## Setting Up the Environment

### 1️ **Create a Virtual Environment**

Create a virtual environment:

```bash
python -m venv venv
```

### 2️ **Activate the Virtual Environment**

Activate the virtual environment:

```bash
source venv/bin/activate  # On Windows, use venv\Scripts\activate
```

### 3️ **Install Dependencies**

Install all required dependencies using the `requirements.txt` file:

```bash
pip install -r requirements.txt
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

## Running the Azure Function

### 1️ **Set Environment Variables**

Create the `local.settings.json` file. Ensure that the file contains the correct MongoDB connection string:

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

### 2️ **Run the Azure Function Locally**

Start the Azure Function locally:

```bash
func start
```

Expected output:

```bash
Functions:

        get_resources_by_batch:  http://localhost:7071/api/resources/find-resources-in-batch

        get_resource_by_id:  http://localhost:7071/api/resources/find-resource-by-id

        search_resources:  http://localhost:7071/api/resources/search
```

## Testing the Function

### **Using Python Script**

Run the test script, ensuring that Azure Functions is running locally:

```bash
python3 -m unittest resources_api_tests.py -v
```
