<p>
    <img style="display: block; margin: 0 auto;" src="https://github.com/pyautoml/rotating-proxy/blob/main/circuit_rotator_cover.png" alt="pyautoml Code2Doc AI-enchanced automatic documentation"/>
</p>


# Lincense & Usage 🐍
* Version: 1.0.0
* Author: pyautoml
* Github: https://github.com/pyautoml
* Name: Code2Docs
* License: CC BY-NC. This work is licensed under a Creative Commons Attribution-NonCommercial 4.0 International License.

1. The quality of the documentation depends on the models used, hardware resources, prompt quality, and input data. 
2. It is recommended to try different combinations to achieve high-quality results. At least 8GB of RAM is recommended for optimal performance.
3. The author of the code is not responsible for its use. The code is published for educational purposes.

# Code2Docs
Code2Docs is an automated documentation generator for source code repositories. 
It processes code, extracts information, generates embeddings, and creates comprehensive 
documentation using LLMs and customizable templates.

## Project Flow
```bash
📂 Repository Data (SQLite + Qdrant)
    ↓
🧠 Context Manager (handles 128K limitation)
    ↓
✍️ Writer Agent (Llama3.1:8b) ←→ 📋 Template System
    ↓
📝 Generated Documentation
    ↓
🔍 Reviewer Agent (Qwen2.5:7b) ←→ 📋 Template System
    ↓
📊 Score & Feedback (0-100%)
    ↓
🔄 Iteration Loop (until 85% or max loops)
    ↓
✅ Final Documentation
```

## Project Structure

- `main.py` – Main entry point for ETL and documentation generation.
- `config/` – Configuration files, secrets, and documentation templates.
- `src/` – Application logic:
  - `core/` – Repository management, configuration, paths.
  - `database/` – Database operations, embedding storage.
  - `documentation/` – Documentation generators and templates.
  - `embeddings/` – Embedding generation and providers.
  - `extraction/` – File and repository extraction utilities.
  - `intelligence/` – Adaptive processing, classification, optimization.
  - `models/` – Data models for repositories, documents, embeddings.
  - `processing/` – Chunking, ETL loading, hybrid extractors.
  - `system/` – Logging, monitoring, exception handling.
  - `workflow/` – Orchestration and workflow management.
- `storage/` – Stores repositories, generated documentation, and databases.

## Requirements

- Python 3.12+
- Install dependencies from `requirements.txt` (if available)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the main script to start ETL and documentation generation:

```bash
python main.py
```

## Features
- Automatic processing of multiple code repositories
- Embedding generation and storage in Qdrant
- Documentation generation using LLMs and templates
- Detailed logging and error handling

## Configuration

- `config/settings.toml` – Main system settings
- `config/secrets.toml` – API keys and secrets
- `config/templates/` – Documentation templates

## Data Storage

- `storage/repositories/` – Source code repositories
- `storage/documentation/` – Generated documentation
- `storage/database/` – Embedding databases

## Troubleshooting

- Check logs for errors and progress
- Ensure write permissions for `storage/` directories
- Verify compatibility of Python and dependencies
