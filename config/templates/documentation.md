# Senior-Level Documentation Template

## Instructions for LLM Agent

When creating documentation for software projects, follow this comprehensive template to ensure senior-level quality and completeness. Adapt sections as needed based on project complexity and requirements.

---

# {{Project Name}}

## Project Description
- **Goal Achieved:**  
  {{Briefly describe the main goal the project achieves}}

- **Main Purpose:**  
  {{Explain the main purpose of the project or script}}

- **Creation Date:**  
  {{Project creation date (e.g., YYYY-MM-DD)}}

- **Version:**  
  {{Current project version (e.g., v0.0.1)}}

- **Status:**  
  {{Development status: In Development | Testing | Production | Deprecated}}

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Technical Stack](#technical-stack)
3. [Prerequisites](#prerequisites)
4. [Installation & Setup](#installation--setup)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [API Documentation](#api-documentation)
8. [Error Handling](#error-handling)
9. [Performance Considerations](#performance-considerations)
10. [Security Considerations](#security-considerations)
11. [Testing](#testing)
12. [Deployment](#deployment)
13. [Monitoring & Logging](#monitoring--logging)
14. [Troubleshooting](#troubleshooting)
15. [Contributing](#contributing)
16. [Changelog](#changelog)

---

## Architecture Overview

### System Architecture
{{Describe the overall system architecture, including major components and their interactions}}

### Data Flow
{{Explain how data flows through the system, including input/output processing}}

### Design Patterns
{{List and briefly explain any design patterns used (e.g., Factory, Observer, Strategy)}}

### Dependencies
{{List major dependencies and their purposes}}

---

## Technical Stack

### Core Technologies
- **Language:** {{Programming language and version}}
- **Framework:** {{Primary framework(s) used}}
- **Database:** {{Database system and version}}
- **Cache:** {{Caching solution if applicable}}

### Development Tools
- **Version Control:** {{Git workflow, branching strategy}}
- **CI/CD:** {{Continuous integration/deployment tools}}
- **Testing:** {{Testing frameworks and tools}}
- **Code Quality:** {{Linting, formatting, static analysis tools}}

### Infrastructure
- **Environment:** {{Development, staging, production environments}}
- **Containerization:** {{Docker, Kubernetes, etc.}}
- **Cloud Services:** {{AWS, GCP, Azure services used}}

---

## Prerequisites

### System Requirements
- {{Operating system requirements}}
- {{Hardware requirements (CPU, RAM, storage)}}
- {{Network requirements}}

### Software Dependencies
- {{Required software and versions}}
- {{Package managers}}
- {{Development tools}}

### Access Requirements
- {{Required permissions or credentials}}
- {{API keys or tokens needed}}
- {{Database access requirements}}

---

## Installation & Setup

### Local Development Setup
```bash
# Clone the repository
git clone {{repository-url}}
cd {{project-directory}}

# Install dependencies
{{installation-commands}}

# Set up environment
{{environment-setup-commands}}
```

### Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
{{configuration-instructions}}
```

### Database Setup
```sql
-- Database initialization
{{database-setup-commands}}
```

### Verification
```bash
# Verify installation
{{verification-commands}}
```

---

## Configuration

### Environment Variables
| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| {{VAR_NAME}} | {{Description}} | {{Default value}} | {{Yes/No}} |

### Configuration Files
- **{{config-file-name}}:** {{Purpose and key settings}}
- **{{another-config-file}}:** {{Purpose and key settings}}

### Runtime Configuration
{{Explain any runtime configuration options and how to modify them}}

---

## Usage Examples

### Basic Usage
```python
# Basic example
{{basic-code-example}}
```

### Advanced Usage
```python
# Advanced example with error handling
{{advanced-code-example}}
```

### Common Use Cases
{{Describe 3-5 common use cases with code examples}}

---

## API Documentation

### Endpoints Overview
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| {{HTTP-METHOD}} | {{/api/endpoint}} | {{Description}} | {{Yes/No}} |

### Request/Response Examples
```json
// Request
{
  "{{parameter}}": "{{value}}"
}

// Response
{
  "{{field}}": "{{value}}",
  "status": "success"
}
```

### Authentication
{{Describe authentication mechanism and how to obtain/use tokens}}

### Rate Limiting
{{Explain rate limiting policies and headers}}

---

## Error Handling

### Error Codes
| Code | Description | Resolution |
|------|-------------|------------|
| {{ERROR-CODE}} | {{Description}} | {{How to resolve}} |

### Exception Handling
```python
# Exception handling pattern
try:
    {{operation}}
except {{SpecificException}} as e:
    {{error-handling-logic}}
```

### Logging Strategy
{{Explain logging levels, formats, and where logs are stored}}

---

## Performance Considerations

### Scalability
{{Discuss scalability limitations and solutions}}

### Optimization Guidelines
{{List performance optimization techniques used}}

### Monitoring Metrics
{{Key performance metrics to monitor}}

### Resource Usage
{{Expected resource consumption patterns}}

---

## Security Considerations

### Authentication & Authorization
{{Describe security mechanisms implemented}}

### Data Protection
{{Explain data encryption, sanitization, and protection measures}}

### Vulnerability Management
{{Security scanning, dependency updates, etc.}}

### Compliance
{{Any compliance requirements (GDPR, SOC2, etc.)}}

---

## Testing

### Test Structure
```
tests/
├── unit/
├── integration/
├── e2e/
└── fixtures/
```

### Running Tests
```bash
# Run all tests
{{test-command}}

# Run specific test suite
{{specific-test-command}}

# Generate coverage report
{{coverage-command}}
```

### Test Coverage
{{Current test coverage percentage and goals}}

### Testing Strategy
{{Explain testing approach and standards}}

---

## Deployment

### Deployment Environments
{{Describe different deployment environments and their purposes}}

### Deployment Process
```bash
# Production deployment
{{deployment-commands}}
```

### Database Migrations
```bash
# Run migrations
{{migration-commands}}
```

### Rollback Procedures
{{Explain how to rollback deployments if issues occur}}

---

## Monitoring & Logging

### Application Monitoring
{{Tools and dashboards used for monitoring}}

### Log Management
{{Where logs are stored and how to access them}}

### Alerting
{{Alert conditions and notification channels}}

### Health Checks
{{Endpoint URLs and expected responses}}

---

## Troubleshooting

### Common Issues
| Issue | Symptoms | Solution |
|-------|----------|----------|
| {{Issue description}} | {{How to identify}} | {{How to resolve}} |

### Debug Mode
{{How to enable debug mode and what additional information it provides}}

### Support Contacts
{{Who to contact for different types of issues}}

---

## Contributing

### Development Workflow
1. {{Step-by-step contribution process}}
2. {{Code review requirements}}
3. {{Testing requirements}}

### Code Standards
{{Coding standards and style guidelines}}

### Pull Request Template
{{Link to or include PR template}}

---

## Changelog

### Version {{X.X.X}} - {{YYYY-MM-DD}}
#### Added
- {{New features}}

#### Changed
- {{Modified features}}

#### Fixed
- {{Bug fixes}}

#### Deprecated
- {{Deprecated features}}

#### Removed
- {{Removed features}}

#### Security
- {{Security improvements}}

---

## Additional Resources

### Documentation Links
- {{Link to additional documentation}}
- {{Link to API reference}}
- {{Link to tutorials}}

### Related Projects
- {{Links to related or dependent projects}}

### Community
- {{Links to community resources, forums, or chat}}

---

## License
{{License information}}

## Support
{{Support contact information and procedures}}

---

*Last updated: {{YYYY-MM-DD}}*
*Document version: {{doc-version}}*