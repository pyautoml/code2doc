#!/usr/bin/env python3

import os
import git
import stat
import json
import shutil
import logging
from pathlib import Path
from filelock import FileLock
from typing import List, Optional
from urllib.parse import urlparse, ParseResult
from src.models.repository import RepositorySource
from concurrent.futures import ThreadPoolExecutor, as_completed


logger: logging.Logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


class ETLExtractor:

    def __init__(
        self,
        storage_path: Path | str,
        max_workers: int = 10,
        github_token: Optional[str] = None,
        redownload: bool = False,
    ):
        self.storage_path: Path = Path(storage_path).resolve()
        self.max_workers: int = max_workers
        self.github_token: Optional[str] = github_token
        self.redownload: bool = redownload

        if not self.storage_path.exists():
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created storage directory at {self.storage_path}")
        self._make_writable(self.storage_path)

    def __str__(self) -> str:
        return json.dumps(
            {
                "storage_path": self.storage_path,
                "max_workers": self.max_workers,
                "github_token": (
                    self.github_token
                    if self.github_token[:3] + "..."
                    else "Not provided"
                ),
            },
            indent=4,
            ensure_ascii=False,
        )

    def __repr__(self) -> str:
        return json.dumps(
            {
                "storage_path": self.storage_path,
                "max_workers": self.max_workers,
                "github_token": (
                    self.github_token
                    if self.github_token[:3] + "..."
                    else "Not provided"
                ),
            },
            indent=4,
            ensure_ascii=False,
        )

    def clone(
        self, repositories: List[RepositorySource], redownload: bool = False
    ) -> List[Optional[Path]]:
        lock_path = self.storage_path / ".clone.lock"
        with FileLock(str(lock_path)):
            downloaded_repos: int = 0

            if not redownload:
                logger.debug("Looking for locally missing repositories to clone.")
                existing_repo_names = {
                    self._get_repo_name(repo.as_posix())
                    for repo in self._get_existing_repositories()
                }
                repositories = [
                    repo
                    for repo in repositories
                    if self._get_repo_name(repo.source) not in existing_repo_names
                ]

            if not repositories:
                logger.info("No new repositories to clone.")
                return []

            with ThreadPoolExecutor(max_workers=max(10, self.max_workers)) as executor:
                future_to_url = {
                    executor.submit(
                        self._clone_single_repository, repository.source
                    ): repository
                    for repository in repositories
                }
                for future in as_completed(future_to_url):
                    repository = future_to_url[future]
                    try:
                        success = future.result()
                        if success:
                            downloaded_repos += 1
                    except Exception as e:
                        logger.warning(
                            f"Unexpected error processing {repository.source}: {e}"
                        )
            logger.info(
                f"Successfully downloaded {downloaded_repos} online repository(-ies)"
            )
            return self._get_existing_repositories()

    @staticmethod
    def _get_repo_name(url: str) -> str:
        parsed: ParseResult = urlparse(url)
        repo_name: str = Path(parsed.path).name
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        return repo_name

    def _prepare_url_with_token(self, url: str) -> str:
        if self.github_token and "github.com" in url:
            if url.startswith("https://"):
                # Remove https:// and add token
                url_without_https = url[8:]
                return f"https://{self.github_token}@{url_without_https}"
        return url

    @staticmethod
    def _make_writable(path: Path) -> None:
        try:
            if path.exists():
                if path.is_file():
                    path.chmod(stat.S_IWRITE | stat.S_IREAD)
                elif path.is_dir():
                    for item in path.rglob("*"):
                        if item.is_file():
                            item.chmod(stat.S_IWRITE | stat.S_IREAD)
        except Exception as e:
            logger.warning(f"Could not make {path} writable: {e}")

    def _clone_single_repository(self, url: str) -> bool:
        try:
            repo_name = self._get_repo_name(url)
            target_path = self.storage_path / repo_name

            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)

            auth_url = self._prepare_url_with_token(url)
            if self.github_token and "github.com" in url:
                logger.debug("Using GitHub token for authentication.")

            logger.debug(f"Cloning repository {auth_url} to {target_path}")
            git.Repo.clone_from(auth_url, target_path)
            logger.debug(f"Repository {auth_url} cloned successfully.")
            return True

        except git.GitCommandError as e:
            logger.error(f"Git error cloning {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error cloning {url}: {e}")
            return False

    def _get_existing_repositories(self) -> List[Path]:
        if not self.storage_path.exists():
            return []
        return [item for item in self.storage_path.iterdir() if item.is_dir()]
