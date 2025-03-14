import pytest
import os
import sys

# Add the src directory to the path so pytest can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))