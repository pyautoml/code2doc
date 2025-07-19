#!/usr/bin/env python3

import os
import logging
import validators
from pathlib import Path
from typing import List, Tuple, Optional
from src.models.document import Document
from src.models.repository import RepositorySource
from src.models.document_metadata import DocumentMetadata


logger: logging.Logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


def split_repositories_by_source(
    sources: List[str],
) -> Optional[Tuple[List[RepositorySource], List[RepositorySource]]]:
    if not sources:
        logger.warning("No repository sources provided. Existing.")
        return None

    online_repositories: List[RepositorySource] = []
    local_repositories: List[RepositorySource] = []

    for source in sources:
        if source:
            if source.startswith("http"):
                if validators.url(source):
                    online_repositories.append(
                        RepositorySource(source=source, type="online")
                    )
                else:
                    logger.warning(f"Invalid URL format: {source}")
            elif source.startswith("github.com"):
                full_url = "https://" + source
                if validators.url(full_url):
                    online_repositories.append(
                        RepositorySource(source=full_url, type="online")
                    )
                else:
                    logger.warning(f"Invalid GitHub URL format: {source}")
            elif source.startswith("www"):
                logger.warning(
                    f"Removing incorrect url from further processing: {source}"
                )
                continue
            else:
                if Path(source).exists():
                    local_repositories.append(
                        RepositorySource(source=source, type="local")
                    )
                else:
                    logger.warning(
                        f"Removing incorrect path from further processing: {source}"
                    )
                    continue

    if not online_repositories and not local_repositories:
        raise ValueError(
            "No valid repositories found. Please provide a list of repository URLs or paths."
        )
    return online_repositories, local_repositories


def load_files(path: str | Path) -> List[Document]:
    """Load all files from a repository path and create Document objects"""
    path: Path = Path(path)

    if not path.exists():
        logger.error(f"Path {path} does not exist.")
        return []

    files = []
    repo_name = path.name

    # List of binary file extensions to skip
    binary_extensions = {
        ".png",".jpg",".gif",".bmp",
        ".tiff",".pdf", ".doc",".docx",
        ".xls",".xlsx",".ppt",".pptx",
        ".zip",".tar", ".gz",".rar",
        ".7z",".exe", ".dll",".so",
        ".dylib",".mp3",".mp4",".avi",
        ".mov",".wav",".bin", ".dat",
        ".db",".sqlite",
    }

    for file in path.rglob("*"):
        if file.is_file():
            try:
                # Skip binary files
                if file.suffix.lower() in binary_extensions:
                    logger.debug(f"Skipping binary file: {file}")
                    continue

                # Skip very large files (>10MB)
                file_size = file.stat().st_size
                if file_size > 10 * 1024 * 1024:  # 10MB
                    logger.debug(f"Skipping large file: {file} ({file_size} bytes)")
                    continue

                metadata: DocumentMetadata = DocumentMetadata(
                    doc_type=file.suffix.lstrip(".") if file.suffix else "unknown",
                    file_size=file_size,
                    last_modified=file.stat().st_mtime,
                )

                try:
                    content = file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    try:
                        content = file.read_text(encoding="latin1")
                    except Exception as e:
                        logger.warning(
                            f"Could not read file {file} due to encoding issues: {e}"
                        )
                        continue

                if not content.strip():
                    logger.debug(f"Skipping empty file: {file}")
                    continue

                document = Document.create(
                    content=content,
                    file_path=file,
                    repo_name=repo_name,
                    metadata=metadata,
                )
                files.append(document)
                logger.debug(f"Loaded file: {file}")

            except Exception as e:
                logger.error(f"Error reading file {file}: {e}")
                continue
    logger.info(f"Successfully loaded {len(files)} files from {path}")
    return files
