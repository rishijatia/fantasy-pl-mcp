#!/usr/bin/env python3

import json
import argparse
import requests
from collections import defaultdict
from typing import Any, Dict, List, Set, Union


def infer_type(value: Any) -> str:
    """Infer the type of a JSON value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return str(type(value))


def extract_array_schema(arr: List[Any]) -> Dict[str, Any]:
    """Extract schema from an array."""
    if not arr:
        return {"type": "array", "items": {}}

    # Analyze all items to see if they're consistent
    item_types = set()
    object_schemas = []
    array_schemas = []

    for item in arr:
        item_type = infer_type(item)
        item_types.add(item_type)
        
        if item_type == "object":
            object_schemas.append(extract_schema(item))
        elif item_type == "array" and item:
            array_schemas.append(extract_array_schema(item))

    # If all items are objects with the same structure
    if len(item_types) == 1 and "object" in item_types and object_schemas:
        # Merge all object schemas
        merged_schema = object_schemas[0]
        for schema in object_schemas[1:]:
            for key, value in schema.get("properties", {}).items():
                if key not in merged_schema["properties"]:
                    merged_schema["properties"][key] = value
                    if key not in merged_schema.get("required", []) and "required" in schema and key in schema["required"]:
                        merged_schema.setdefault("required", []).append(key)
        
        return {
            "type": "array",
            "items": merged_schema
        }
    
    # If all items are arrays with potentially the same structure
    elif len(item_types) == 1 and "array" in item_types and array_schemas:
        # Use the first array schema as representative
        return {
            "type": "array",
            "items": array_schemas[0]
        }
    
    # Different types in the array
    elif len(item_types) > 1:
        return {
            "type": "array",
            "items": {
                "oneOf": [{"type": t} for t in item_types]
            }
        }
    
    # Simple array of primitive types
    else:
        return {
            "type": "array",
            "items": {
                "type": list(item_types)[0] if item_types else "any"
            }
        }


def extract_schema(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Extract JSON schema from a dictionary."""
    if not isinstance(obj, dict):
        return {"type": infer_type(obj)}
    
    properties = {}
    required = []
    
    for key, value in obj.items():
        value_type = infer_type(value)
        
        if value_type == "object":
            properties[key] = extract_schema(value)
        elif value_type == "array":
            properties[key] = extract_array_schema(value)
        else:
            properties[key] = {"type": value_type}
            
        # Consider all non-null properties as required for simplicity
        if value is not None:
            required.append(key)
    
    schema = {
        "type": "object",
        "properties": properties
    }
    
    if required:
        schema["required"] = required
        
    return schema


def analyze_json_structure(data: Any) -> Dict[str, Any]:
    """Analyze the structure of JSON data and return statistics and schema."""
    structure = {}
    
    # Get the type of the root
    root_type = infer_type(data)
    structure["root_type"] = root_type
    
    # Extract schema
    if root_type == "object":
        structure["schema"] = extract_schema(data)
    elif root_type == "array":
        structure["schema"] = extract_array_schema(data)
    else:
        structure["schema"] = {"type": root_type}
    
    # Add some statistics
    structure["stats"] = analyze_statistics(data)
    
    return structure


def analyze_statistics(data: Any) -> Dict[str, Any]:
    """Generate statistics about the JSON data."""
    stats = {}
    
    if isinstance(data, dict):
        stats["property_count"] = len(data)
        
        # Count nested objects and arrays
        nested_objects = 0
        nested_arrays = 0
        
        for key, value in data.items():
            if isinstance(value, dict):
                nested_objects += 1
            elif isinstance(value, list):
                nested_arrays += 1
                
        stats["nested_objects"] = nested_objects
        stats["nested_arrays"] = nested_arrays
        
    elif isinstance(data, list):
        stats["array_length"] = len(data)
        
        # Analyze array items
        if data:
            types = defaultdict(int)
            for item in data:
                types[infer_type(item)] += 1
            stats["item_types"] = dict(types)
    
    return stats


def fetch_json_from_url(url: str) -> Any:
    """Fetch JSON data from a URL."""
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for 4XX/5XX errors
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Extract schema from JSON data at a URL")
    parser.add_argument("url", help="URL to fetch JSON data from")
    parser.add_argument("-o", "--output", help="Output file for the schema (default is stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the output JSON")
    
    args = parser.parse_args()
    
    try:
        # Fetch the JSON data
        data = fetch_json_from_url(args.url)
        
        # Analyze the structure
        result = analyze_json_structure(data)
        
        # Prepare the output
        indent = 2 if args.pretty else None
        output = json.dumps(result, indent=indent)
        
        # Write the output
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Schema written to {args.output}")
        else:
            print(output)
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())