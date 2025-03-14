# Contributing to Fantasy PL MCP

Thank you for considering contributing to this project! We welcome contributions from everyone who is interested in improving Fantasy PL MCP.

## Ways to Contribute

There are many ways to contribute to the project:

- Reporting bugs
- Suggesting enhancements
- Writing documentation
- Submitting code changes
- Helping others use the project

## Development Environment Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/fantasy-pl-mcp.git
   cd fantasy-pl-mcp
   ```

3. Create a virtual environment:
   ```bash
   cd server
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Development Workflow

1. Create a new branch for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Test your changes:
   - Run the server with the MCP Inspector
   - Test all affected resources, tools, and prompts
   - Verify that no regressions have been introduced

4. Commit your changes:
   ```bash
   git commit -am "Add a descriptive message about your changes"
   ```

5. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Create a Pull Request from your branch to the main repository

## Pull Request Guidelines

- Update documentation if you're changing functionality
- Add tests for any new features
- Ensure your code follows the project's style conventions
- Make sure all tests pass
- Keep pull requests focused on a single topic

## Reporting Bugs

When reporting a bug, please include:

- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Screenshots or logs if applicable
- Environment information (OS, Python version, etc.)

## Feature Requests

For feature requests, please include:

- A clear, descriptive title
- A detailed description of the proposed feature
- Any relevant context or examples
- Potential implementation approach (if you have ideas)

## Code of Conduct

Please be respectful and considerate of others when participating in this project. We want to maintain a welcoming and inclusive environment for everyone.

## Questions?

If you have any questions about contributing, please open an issue with your question.