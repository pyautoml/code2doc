#!/usr/bin/env python3
# Author: https://github.com/pyautoml/pyautoml
# License: CC BY-NC

import os
import logging
from pathlib import Path
from typing import List, Optional
from src.core.bootstrap import Bootstrap
from src.workflow.orchestration import ETLWorkflow
from src.database.qdrant_writer import QdrantBatchWriter
from src.core.repository_manager import RepositoryManager
from src.processing.repositories_input import process_input_resources
from src.documentation.report import analyze_repository_content, generate_comprehensive_documentation


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


def main(
    repositories: List[Optional[str]],
    skip_etl: bool = False,
    remove_temp_files: bool = False,
    update_repositories: bool = False,
    generate_docs: bool = True,
    analyze_content: bool = True,
) -> None:
    """
    Working main function with fixed documentation generation

    Args:
        repositories: List of repository URLs or paths
        skip_etl: Skip ETL and only generate documentation
        remove_temp_files: Clean up temporary files after processing
        update_repositories: Update existing repositories
        generate_docs: Generate documentation after ETL
        analyze_content: Analyze repository content before documentation
    """
    bootstrap = Bootstrap()
    bootstrap.run()

    batch_writer = QdrantBatchWriter.get_instance()
    repo_manager = RepositoryManager(batch_writer)

    if skip_etl:
        logger.info(
            "Skipping ETL processing. Analyzing existing database and generating documentation."
        )
        if analyze_content:
            analyze_repository_content()
        if generate_docs:
            generate_comprehensive_documentation()
        return

    online_repositories, local_repositories = process_input_resources(repositories)
    all_repo_sources = [
        repo.source for repo in online_repositories + local_repositories
    ]

    # Log repository status before processing
    status = repo_manager.get_repository_status(all_repo_sources)
    logger.info(
        f"Repository Status: {status['total_repositories']} total "
        f"({status['local_repositories']} local, {status['online_repositories']} online), "
        f"{status['existing_in_db']} already in database"
    )

    if update_repositories:
        logger.info("Update mode: checking for repository changes...")

        local_repos_to_update = []
        for repo in local_repositories:
            if repo.source in repo_manager.check_repository_changes([repo.source]):
                local_repos_to_update.append(repo)

        if online_repositories:
            logger.info("Online repositories will be re-downloaded for change detection")
            repo_manager.cleanup_repository_data(
                [repo.source for repo in online_repositories]
            )

        if local_repos_to_update:
            repo_manager.cleanup_repository_data(
                [repo.source for repo in local_repos_to_update]
            )
            local_repositories = local_repos_to_update
        else:
            local_repositories = []  # No local repos need updating

    else:
        existing_repos = batch_writer.get_existing_repository_sources(all_repo_sources)
        if existing_repos:
            logger.info(f"Found {len(existing_repos)} existing repositories in database")
            repo_manager.cleanup_repository_data(existing_repos)

    workflow = ETLWorkflow()
    workflow.run(
        online_repositories=online_repositories,
        local_repositories=local_repositories,
        update_repositories=update_repositories,
    )

    if update_repositories:
        for repo in local_repositories:
            if Path(repo.source).exists():
                repo_manager.update_repository_hash(repo.source)

    stats = workflow.batch_writer.get_repository_stats()
    logger.info(f"✅ ETL Complete: Processed {stats['total_repositories']} repositories")

    if analyze_content:
        analyze_repository_content()

    if generate_docs:
        logger.info("📝 Starting comprehensive documentation generation...")
        generate_comprehensive_documentation()

    if remove_temp_files:
        storage_path = Path("storage/repositories")
        repo_manager.cleanup_temp_files(storage_path)

    logger.info("Enhanced ETL + Comprehensive Documentation Complete!")

    final_stats = batch_writer.get_repository_stats()
    logger.debug(f"\n📈 Final Summary:")
    logger.debug(f"   • Total repositories in database: {final_stats['total_repositories']}")
    logger.debug(f"   • Total chunks available for analysis: {final_stats['total_chunks']}")
    logger.debug(f"   • Documentation files in storage/documentation/")


if __name__ == "__main__":
    repos = [
        # urls or a path to locally stored repositories
        "https://github.com/pyautoml/circuit-rotator",
        "https://github.com/pyautoml/python-module-dependency",
    ]

    main(
        repositories=repos,
        skip_etl=False,             # Skip ETL, just generate docs from existing data
        update_repositories=False,  # Don't update, use existing data
        remove_temp_files=False,    # Don't remove files
        generate_docs=True,         # Generate documentation
        analyze_content=True,       # Analyze content first
    )
