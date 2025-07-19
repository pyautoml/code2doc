# Documentation Generation Instructions for Writer Agent

## CRITICAL UNDERSTANDING
You are creating ACTUAL documentation, NOT a template. All placeholders in curly braces {{like this}} must be replaced with real information from the project analysis provided to you.

**NEVER output placeholder text like {{Project Name}} or {{Description}}**
**ALWAYS replace ALL placeholders with actual project information**

## Your Task
Analyze the provided project context and create complete, professional documentation following this structure. Fill in every section with real information based on the project analysis.

---

# [ACTUAL PROJECT NAME - Replace with real name from context]

## Project Description
- **Goal Achieved:** [Write the actual main goal this project achieves based on analysis]
- **Main Purpose:** [Describe the actual purpose based on code analysis]  
- **Creation Date:** [Use actual date or current date: YYYY-MM-DD]
- **Version:** [Extract from package.json/setup.py/etc. or use v1.0.0]
- **Status:** [Choose: In Development | Testing | Production | Deprecated]

---

## Quick Start 🚀
[Provide 3-5 commands that get a developer up and running immediately]

```bash
# Example - replace with actual commands
git clone [actual-repo-url]
cd [actual-directory-name]
pip install -r requirements.txt
python main.py
```

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Technical Stack](#technical-stack)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Usage Examples](#usage-examples)
6. [API Documentation](#api-documentation)
7. [Error Handling](#error-handling)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Architecture
[Describe the actual architecture type found in analysis - e.g., "This is a FastAPI-based REST API with PostgreSQL database" or "This is a Django web application with Redis caching"]

```mermaid
graph TD
    A[Actual Component 1] --> B[Actual Component 2]
    B --> C[Actual Component 3]
    %% Replace with real components from your analysis
```

### Key Components
[List the actual main modules/classes found in the project analysis]
- **[Actual Module Name]:** [Actual purpose from code analysis]
- **[Another Module]:** [Its actual purpose]

### Data Flow
[Explain how data actually flows through this specific system based on the code]

---

## Technical Stack

### Core Technologies
- **Language:** [Actual language and version from analysis - e.g., Python 3.9+]
- **Framework:** [Actual framework found - e.g., FastAPI, Django, Flask]
- **Database:** [Actual database if found - e.g., PostgreSQL, SQLite, MongoDB]
- **Cache:** [Actual caching if found - e.g., Redis, Memcached, or "None"]

### Dependencies
[List actual dependencies found in requirements.txt, package.json, etc.]
```bash
# Main dependencies (replace with actual ones)
fastapi==0.104.1
sqlalchemy==2.0.23
pydantic==2.5.0
```

---

## Installation & Setup

### Prerequisites
- [Actual system requirements based on project]
- [Actual software dependencies found]

### Installation Steps
```bash
# Replace with actual installation commands
git clone [actual-repo-url]
cd [actual-project-directory]

# Install dependencies - use actual command
pip install -r requirements.txt
# OR
npm install
# OR 
poetry install

# Database setup if applicable
python manage.py migrate
# OR
alembic upgrade head
```

### Environment Configuration
```bash
# Replace with actual environment setup
cp .env.example .env
# Edit .env with required values:
# - DATABASE_URL=postgresql://user:pass@localhost/dbname
# - API_KEY=your_api_key_here
```

---

## Configuration

### Environment Variables
[Create table with ACTUAL variables found in .env files or config files]

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| DATABASE_URL | Database connection string | Yes | None |
| API_KEY | External API authentication | Yes | None |
| PORT | Server port | No | 8000 |

### Configuration Files
[List actual config files found in project]
- **config.py:** [Actual purpose based on file content]
- **settings.json:** [Actual purpose based on file content]

---

## Usage Examples

### Basic Usage
```python
# Replace with actual code examples from the project
from actual_module import ActualClass

client = ActualClass(api_key="your_key")
result = client.actual_method("real_parameter")
print(result)
```

### Advanced Usage
```python
# Show actual advanced features found in the code
from actual_module import ActualAdvancedClass

# Real example based on actual code analysis
advanced_client = ActualAdvancedClass(
    config_param="actual_value",
    timeout=30
)

try:
    response = advanced_client.complex_operation(
        param1="real_value",
        param2={"actual": "data"}
    )
    print(f"Success: {response}")
except ActualException as e:
    print(f"Error: {e}")
```

---

## API Documentation

[Include this section ONLY if API endpoints were found in the analysis]

### Endpoints
[List actual endpoints found in the code]

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | /api/actual-endpoint | Real endpoint description | Yes |
| POST | /api/another-endpoint | Another real endpoint | No |

### Request/Response Examples
```json
// Actual API request example
POST /api/actual-endpoint
{
  "real_parameter": "actual_value",
  "another_param": 123
}

// Actual response format
{
  "status": "success",
  "data": {
    "id": "actual_id_format",
    "result": "actual_result_structure"
  }
}
```

---

## Error Handling

### Common Error Codes
[List actual error handling found in the code]

| Error | Description | Solution |
|-------|-------------|----------|
| ConnectionError | Database connection failed | Check DATABASE_URL configuration |
| ValidationError | Invalid input parameters | Verify request format |

### Exception Handling Pattern
```python
# Show actual error handling patterns from the code
try:
    result = actual_function_call()
except SpecificException as e:
    logger.error(f"Specific error occurred: {e}")
    # Actual error handling logic
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Actual fallback logic
```

---

## Testing

### Running Tests
```bash
# Use actual test commands found in project
pytest tests/
# OR
python -m unittest discover
# OR
npm test
```

### Test Structure
[Describe actual test structure if tests folder exists]
```
tests/
├── unit/
├── integration/
└── fixtures/
```

---

## Troubleshooting

### Common Issues

#### Issue: [Actual common issue based on code analysis]
**Symptoms:** [How to identify this issue]
**Solution:** 
```bash
# Actual solution commands
actual-command --fix-parameter
```

#### Issue: [Another actual issue]
**Symptoms:** [Actual symptoms]
**Solution:** [Actual solution steps]

---

## Development

### Project Structure
```
[actual-project-name]/
├── [actual-main-directory]/
│   ├── [actual-module].py
│   └── [another-module].py
├── tests/
├── requirements.txt
└── README.md
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `[actual-test-command]`
5. Submit a pull request

---

## Additional Resources
- **Repository:** [actual-repository-url]
- **Documentation:** [actual-docs-url if found]
- **Issues:** [actual-issues-url]

---

*Documentation generated on: [current-date]*
*Project Version: [actual-version]*

## WRITER AGENT CHECKLIST
Before submitting documentation, verify:
- [ ] All {{placeholder}} text has been replaced with actual information
- [ ] All code examples use actual project code and imports
- [ ] All file paths and directory names are real
- [ ] All configuration variables are from actual config files
- [ ] All API endpoints are from actual code analysis
- [ ] All dependencies are from actual requirement files
- [ ] Project name, description, and purpose are specific to this project
- [ ] Installation commands work with this specific project
- [ ] Examples can actually be executed with this project