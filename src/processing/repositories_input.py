#!/usr/bin/env python3

import validators
from pathlib import Path
from typing import List, Tuple, Optional
from src.models.repository import RepositorySource
from src.extraction.file_reader import split_repositories_by_source


def process_input_resources(
    repositories: List[Optional[str]],
) -> Tuple[List[Optional[RepositorySource]], List[Optional[RepositorySource]]]:

    if not repositories:
        raise ValueError("No repositories provided. Exiting.")

    online_repositories, local_repositories = _repository_split_with_validation(
        repositories
    )

    if not online_repositories and not local_repositories:
        raise ValueError(
            "No valid repositories provided for ETL processing. Provide a list of repository URLs or paths."
        )

    for repository in repositories:
        if not isinstance(repository, str):
            raise TypeError(
                f"Expected 'repository' to be a string, got {type(repository).__name__}."
            )
        if repository.strip() == "":
            raise ValueError(
                "Empty repository URL or path found. Please provide a valid repository URL or path."
            )

    if not repositories:
        raise ValueError(
            "No valid repository sources after url/path normalization. Exiting."
        )

    if not online_repositories and not local_repositories:
        raise ValueError(
            "No valid repositories provided for ETL processing. Provide a list of repository URLs or paths."
        )

    return online_repositories, local_repositories

def _normalize_source(repository: Optional[str]) -> Optional[str]:
    try:
        repository: str = Path(repository.strip()).as_posix()
        if validators.url(repository) or Path(repository).exists():
            return repository
    except:
        return None

def _repository_split_with_validation(
    repositories: List[Optional[str]],
) -> Optional[Tuple[List[RepositorySource], List[RepositorySource]]]:
    if repositories and not isinstance(repositories, list):
        raise TypeError(
            f"Expected 'repositories' to be a list, got {type(repositories).__name__}."
        )

    if any(not isinstance(repo, (str, type(None))) for repo in repositories):
        raise TypeError(
            "All items in 'repositories' must be strings or None. "
            "Please provide a list of repository URLs or paths."
        )

    if not repositories:
        raise ValueError(
            "No repositories provided. Please provide a list of repository URLs or paths."
        )

    online_repositories, local_repositories = split_repositories_by_source(repositories)

    if not online_repositories and not local_repositories:
        raise ValueError(
            "No valid repositories provided. Please provide a list of repository URLs or paths."
        )

    return online_repositories, local_repositories
