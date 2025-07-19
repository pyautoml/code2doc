#!/usr/bin/env python3

import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from src.core.configuration import ConfigLoader
from src.extraction.repository_extractor import ETLExtractor
from src.models.repository import RepositorySource
from src.intelligence.adaptive_processor import AdaptiveRepositoryProcessor
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.database.qdrant_writer import QdrantBatchWriter


logger: logging.Logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


class ETLWorkflow:
    config: ConfigLoader = ConfigLoader()
    storage: Path = Path(config.get("storage.repositories")).resolve()
    max_workers: int = int(config.get("app.max_workers", 10))

    def __init__(self):
        self.adaptive_processor = AdaptiveRepositoryProcessor(
            max_workers=self.max_workers
        )
        self.batch_writer = QdrantBatchWriter.get_instance()

    def run(
        self,
        online_repositories: List[RepositorySource],
        local_repositories: List[RepositorySource],
        update_repositories: bool = False,
    ):
        logger.info(
            f"Online repositories to process: {len(online_repositories)} "
            f"Local repositories: {len(local_repositories)}"
        )

        if online_repositories:
            logger.debug("Cloning online repositories")
            downloaded_repositories: List[Optional[Path]] = ETLExtractor(
                storage_path=self.storage,
                github_token=self.config.get_secret("token.github"),
                max_workers=self.max_workers,
                redownload=update_repositories,
            ).clone(repositories=online_repositories)

            if downloaded_repositories:
                local_repositories.extend(
                    [
                        RepositorySource(source=str(item), type="local")
                        for item in downloaded_repositories
                        if item is not None
                    ]
                )

        if local_repositories:
            logger.debug("Verifying paths of local repositories")
            initial_repositories: int = len(local_repositories)
            local_repositories: List[RepositorySource] = [
                repository
                for repository in local_repositories
                if Path(repository.source).exists()
            ]
            logger.debug(
                f"Found {len(local_repositories)} valid local repositories "
                f"out of {initial_repositories}"
            )

            successful_uploads = 0
            failed_uploads = 0
            logger.info("Starting adaptive processing of repositories...")

            for i, repository in enumerate(local_repositories, 1):
                logger.info(
                    f"Processing repository {i}/{len(local_repositories)}: {repository.source}"
                )

                try:
                    success = self.adaptive_processor.process_repository_adaptive(repository)

                    if success:
                        successful_uploads += 1
                        logger.info(
                            f"Successfully processed repository: {repository.source}"
                        )
                    else:
                        failed_uploads += 1
                        logger.error(
                            f"Failed to process repository: {repository.source}"
                        )

                except Exception as e:
                    failed_uploads += 1
                    logger.error(
                        f"Exception processing repository {repository.source}: {e}"
                    )

            stats = self.batch_writer.get_repository_stats()
            logger.info(f"   • Successfully processed: {successful_uploads} repositories")
            logger.info(f"   • Failed processing: {failed_uploads} repositories")

            if stats.get("repositories"):
                logger.info("Repository Details:")
                for repo in stats["repositories"][:5]:  # Show top 5 most recent
                    logger.info(
                        f"   • {repo['source']}: {repo['files']} files, {repo['chunks']} chunks"
                    )
                if len(stats["repositories"]) > 5:
                    logger.info(
                        f"   ... and {len(stats['repositories']) - 5} more repositories"
                    )

    def cleanup_downloaded_repos(self) -> None:
        logger.debug("Cleaning up temporary files")
        if self.storage.exists():
            items = list(self.storage.iterdir())
            if not items:
                logger.debug("No files to clean up")
                return

            logger.info(f"Cleaning up {len(items)} items from storage directory")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_item = {}
                for item in items:
                    if item.is_file() or item.is_symlink():
                        future = executor.submit(item.unlink)
                    elif item.is_dir():
                        future = executor.submit(
                            lambda p: shutil.rmtree(p, ignore_errors=True), item
                        )
                    future_to_item[future] = item

                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        future.result()
                        logger.debug(f"Deleted: {item}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {item}: {e}")

            logger.info(f"Cleaned up storage directory: {self.storage}")
        else:
            logger.warning(f"⚠Storage directory does not exist: {self.storage}")

    def get_processing_stats(self) -> dict:
        return self.batch_writer.get_repository_stats()

    def health_check(self) -> bool:
        try:
            stats = self.batch_writer.get_repository_stats()
            storage_exists = self.storage.exists()
            logger.info("🔍 Health Check Results:")
            logger.info(f"   • Database connection: ✅ Working")
            logger.info(
                f"   • Storage directory: {'✅ Exists' if storage_exists else '❌ Missing'}"
            )
            logger.info(f"   • Total repositories in DB: {stats['total_repositories']}")
            return storage_exists
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False
