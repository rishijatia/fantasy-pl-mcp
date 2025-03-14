"""
Mock MCP module for testing.
This allows tests to run without requiring the actual MCP package.
"""

# Mock classes and functions for the MCP package
class FastMCP:
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.resources = {}
        self.tools = {}
    
    def resource(self, path):
        def decorator(func):
            self.resources[path] = func
            return func
        return decorator
    
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

# Mock other classes and functions as needed
class Context:
    def __init__(self):
        self.request_context = RequestContext()

class RequestContext:
    def __init__(self):
        self.lifespan_context = {}
