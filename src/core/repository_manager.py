#!/usr/bin/env python3
import os
import stat
import shutil
import hashlib
import logging
from pathlib import Path
from typing import List, Set
from src.database.qdrant_writer import QdrantBatchWriter


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


class RepositoryManager:

    def __init__(self, batch_writer: QdrantBatchWriter = None):
        self.batch_writer = batch_writer or QdrantBatchWriter.get_instance()

        # File extensions to skip during hash calculation
        self.binary_extensions: Set[str] = {
            ".png",".jpg",".jpeg",".gif",".bmp",
            ".tiff",".ico",".pdf",".doc",".docx",
            ".xls",".xlsx",".ppt",".pptx",".zip",
            ".tar",".gz",".rar",".7z",".exe",".dll",
            ".so",".dylib",".mp3",".mp4",".avi",
            ".mov",".wav",".bin",".dat",".db",".sqlite",
        }

        # Directories to skip during hash calculation
        self.skip_directories: Set[str] = {
            ".git","__pycache__","node_modules",
            ".venv","venv",".pytest_cache",".tox",
            "dist","build",".idea",".vscode",".vs",
            "target","bin","obj",
        }

    def calculate_repository_hash(self, repository_path: str) -> str:
        path = Path(repository_path)
        if not path.exists():
            logger.warning(f"Repository path does not exist: {repository_path}")
            return ""
        file_hashes = []
        processed_files = 0

        try:
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file() and not self._should_skip_file(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            file_content = f.read()
                            file_hash = hashlib.md5(file_content).hexdigest()
                            relative_path = file_path.relative_to(path)
                            file_hashes.append(f"{relative_path}:{file_hash}")
                            processed_files += 1
                    except (IOError, OSError, PermissionError) as e:
                        logger.debug(
                            f"Skipping file due to read error {file_path}: {e}"
                        )
                        continue

            logger.debug(
                f"Processed {processed_files} files for hash calculation in {repository_path}"
            )

            # Create overall repository hash
            combined = "|".join(file_hashes)
            repo_hash = hashlib.md5(combined.encode()).hexdigest()
            return repo_hash
        except Exception as e:
            logger.error(
                f"Error calculating repository hash for {repository_path}: {e}"
            )
            return ""

    def _should_skip_file(self, file_path: Path) -> bool:
        # Check if file is in a directory we should skip
        if any(part in self.skip_directories for part in file_path.parts):
            return True

        if file_path.suffix.lower() in self.binary_extensions:
            return True

        if file_path.name.startswith("."):
            return True

        # Skip very large files (>50MB) to avoid memory issues during hashing
        try:
            if file_path.stat().st_size > 50 * 1024 * 1024:
                logger.debug(
                    f"Skipping large file during hash calculation: {file_path}"
                )
                return True
        except OSError:
            return True

        return False

    def check_repository_changes(self, repositories: List[str]) -> List[str]:
        repos_to_update = []
        for repo_source in repositories:
            try:
                # Skip online repositories - always need to re-download them
                if repo_source.startswith(("http://", "https://")):
                    logger.debug(
                        f"Online repository {repo_source} will be re-downloaded"
                    )
                    repos_to_update.append(repo_source)
                    continue

                # Calculate current hash for local repositories
                current_hash = self.calculate_repository_hash(repo_source)
                if not current_hash:
                    logger.warning(
                        f"Could not calculate hash for {repo_source}, will update"
                    )
                    repos_to_update.append(repo_source)
                    continue

                repo_id = self._generate_repo_id(repo_source)
                stored_hash = self.batch_writer.get_repository_hash(repo_id)
                if stored_hash != current_hash:
                    logger.info(f"Repository {repo_source} has changed (hash mismatch)")
                    repos_to_update.append(repo_source)
                else:
                    logger.info(f"Repository {repo_source} unchanged, skipping")
            except Exception as e:
                logger.error(f"Error checking repository {repo_source}: {e}")
                repos_to_update.append(repo_source)  # Update on error to be safe

        return repos_to_update

    def cleanup_repository_data(self, repositories: List[str]):
        logger.info(f"Cleaning up old repository data for {len(repositories)} repositories")

        cleaned_count = 0
        for repo_source in repositories:
            try:
                # Generate the same repo_id that would be used during processing
                repo_id = self._generate_repo_id(repo_source)

                # Delete from databases
                self.batch_writer.delete_repository_data(repo_id)
                logger.debug(f"Cleaned up data for repository: {repo_source}")
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up repository {repo_source}: {e}")
        logger.info("Successfully cleaned up {cleaned_count}/{len(repositories)} repositories")

    def update_repository_hash(self, repository_source: str, content_hash: str = None):
        try:
            if content_hash is None:
                content_hash = self.calculate_repository_hash(repository_source)

            if content_hash:
                repo_id = self._generate_repo_id(repository_source)
                self.batch_writer.store_repository_hash(repo_id, content_hash)
                logger.debug(f"Updated hash for repository {repository_source}")
            else:
                logger.warning(f"Could not calculate hash for repository {repository_source}")
        except Exception as e:
            logger.error(f"Error updating repository hash for {repository_source}: {e}")

    @staticmethod
    def cleanup_temp_files(storage_path: Path):
        if not storage_path.exists():
            logger.debug(
                f"Storage path {storage_path} does not exist, nothing to clean"
            )
            return

        try:
            items = list(storage_path.iterdir())
            item_count = len(items)

            if item_count == 0:
                logger.debug("No temporary files to clean up")
                return

            logger.info(f"Cleaning up {item_count} items from {storage_path}")

            def onerror(func, path, exc_info):
                if not os.access(path, os.W_OK):
                    os.chmod(path, stat.S_IWUSR)
                    func(path)
                else:
                    logger.warning(f"Could not delete {path}: {exc_info[1]}")

            shutil.rmtree(storage_path, onerror=onerror)
            storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Successfully cleaned up temporary files in {storage_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files in {storage_path}: {e}")

    def get_repository_status(self, repositories: List[str]) -> dict:
        status = {
            "total_repositories": len(repositories),
            "local_repositories": 0,
            "online_repositories": 0,
            "existing_in_db": 0,
            "repositories": [],
        }

        for repo_source in repositories:
            repo_info = {
                "source": repo_source,
                "type": (
                    "online"
                    if repo_source.startswith(("http://", "https://"))
                    else "local"
                ),
                "exists_locally": False,
                "exists_in_db": False,
                "current_hash": None,
                "stored_hash": None,
            }

            # Count types
            if repo_info["type"] == "online":
                status["online_repositories"] += 1
            else:
                status["local_repositories"] += 1
                repo_info["exists_locally"] = Path(repo_source).exists()
                if repo_info["exists_locally"]:
                    repo_info["current_hash"] = self.calculate_repository_hash(
                        repo_source
                    )

            # Check if exists in database
            repo_id = self._generate_repo_id(repo_source)
            stored_hash = self.batch_writer.get_repository_hash(repo_id)
            if stored_hash:
                status["existing_in_db"] += 1
                repo_info["exists_in_db"] = True
                repo_info["stored_hash"] = stored_hash
            status["repositories"].append(repo_info)
        return status

    @staticmethod
    def _generate_repo_id(repository_source: str) -> str:
        source_hash = hashlib.md5(repository_source.encode()).hexdigest()[:12]
        return f"repo_{source_hash}"
