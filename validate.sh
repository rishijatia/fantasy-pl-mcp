#!/bin/bash

echo "Validating Fantasy PL MCP Project..."

# Check file structure
if [ -d "src/fpl_mcp" ]; then
  echo "✅ Source directory structure is correct"
else
  echo "❌ Source directory structure is incorrect"
  exit 1
fi

# Check key files
FILES_TO_CHECK=(
  "src/fpl_mcp/__init__.py"
  "src/fpl_mcp/__main__.py"
  "src/fpl_mcp/config.py"
  "pyproject.toml"
  "install_mcp.py"
  ".github/workflows/python-test.yml"
)

for file in "${FILES_TO_CHECK[@]}"; do
  if [ -f "$file" ]; then
    echo "✅ $file exists"
  else
    echo "❌ $file is missing"
    exit 1
  fi
done

# Check for import references to update
grep -r "from fpl\." --include="*.py" src/fpl_mcp
if [ $? -eq 0 ]; then
  echo "⚠️ Found some potential import issues. Check the above lines."
else
  echo "✅ No problematic imports found"
fi

grep -r "from \.\." --include="*.py" src/fpl_mcp
if [ $? -eq 0 ]; then
  echo "✅ Parent directory relative imports found"
else
  echo "⚠️ No parent relative imports found, which is unexpected"
fi

grep -r "from \." --include="*.py" src/fpl_mcp
if [ $? -eq 0 ]; then
  echo "✅ Current directory relative imports found"
else
  echo "⚠️ No current directory relative imports found, which is unexpected"
fi

# Check for any server directory references
grep -r "server/" --include="*.py" src/fpl_mcp
if [ $? -eq 0 ]; then
  echo "⚠️ Found some potential 'server/' directory references. Check the above lines."
else
  echo "✅ No problematic server directory references found"
fi

echo "Validation complete!"