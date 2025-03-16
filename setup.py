from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fpl-mcp",
    version="0.1.3",
    author="Fantasy PL MCP Contributors",
    author_email="rishi.jatia96@gmail.com",
    description="An MCP server for Fantasy Premier League data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rishijatia/fantasy-pl-mcp",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "mcp>=1.2.0",
        "httpx>=0.24.0",
        "python-dotenv",
        "diskcache",
        "jsonschema",
    ],
    entry_points={
        "console_scripts": [
            "fpl-mcp=fpl_mcp.__main__:main",
        ],
    },
    package_data={
        "fpl_mcp": ["schemas/*.json"],
    },
)