#!/usr/bin/env python3

import gc
import os
import time
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass
from src.models.chunk import Chunk
from src.models.document import Document
from src.models.embedding import Embedding
from typing import List, Tuple, Optional, Set
from src.processing.chunker import ChunkGenerator
from src.models.repository import RepositorySource
from src.embeddings.service import EmbeddingService
from src.database.qdrant_writer import QdrantBatchWriter
from src.extraction.streaming_reader import StreamingFileReader
from src.intelligence.classifier import (
    AdaptiveFileClassifier,
    FileSize,
    FileClassification,
)


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


@dataclass
class ProcessingBatch:
    documents: List[Document]
    chunks: List[Chunk]
    embeddings: List[Embedding]
    memory_used_mb: float
    processing_time: float


class AdaptiveRepositoryProcessor:
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.file_classifier = AdaptiveFileClassifier()
        self.streaming_reader = StreamingFileReader()
        self.chunk_generator = ChunkGenerator()
        self.embedding_service = EmbeddingService()
        self.batch_writer = QdrantBatchWriter.get_instance()  # Use singleton

        self.binary_extensions: Set[str] = {
            ".png",".jpg",".jpeg",".gif",
            ".bmp",".tiff",".ico",".webp",
            ".pdf",".doc",".docx",".xls",
            ".xlsx",".ppt", ".pptx",".zip",
            ".tar",".gz",".rar",".7z",
            ".bz2",".xz",".exe",".dll",
            ".so",".dylib",".msi",".deb",
            ".rpm",".mp3",".mp4",".avi",
            ".mov", ".wav",".flac", ".ogg",
            ".bin", ".dat", ".db",".sqlite",
            ".sqlite3", ".woff", ".woff2",
            ".ttf",".otf",".eot", ".pyc",
            ".pyo", ".pyd", ".class",".jar",
            ".o",".obj", ".lib", ".a",
            ".out", ".iso", ".dmg", ".img",
            ".vdi",".vmdk",
        }

        self.skip_directories: Set[str] = {
            ".git",  ".svn", ".hg", ".bzr",
            "__pycache__",".pytest_cache",
            ".tox",".coverage",  "node_modules",
            ".npm",".yarn",  ".venv", "venv",
            "env", ".env",  "dist", "build",
            "target",  "out",  ".idea",
            ".vscode",".vs",  ".eclipse",
            ".cache",".tmp", "tmp", "temp",
            "logs","log", ".docker",  "docker",
            ".terraform", ".vagrant","vendor",
            "packages"
        }

        self.skip_file_patterns: Set[str] = {
            ".gitignore",".gitattributes",".gitmodules",
            ".dockerignore", "Dockerfile", ".env", ".env.local",
            ".env.production","package-lock.json","yarn.lock",
            "poetry.lock", "Pipfile.lock","requirements.txt",
            ".DS_Store", "Thumbs.db", "desktop.ini", "LICENSE",
            "COPYING","COPYRIGHT", "CHANGELOG","HISTORY", "NEWS",
        }

    def process_repository_adaptive(self, repository: RepositorySource) -> bool:
        logger.info(f"Starting adaptive processing for repository: {repository.source}")
        start_time = time.time()

        try:
            repo_path = Path(repository.source)
            all_files = list(repo_path.rglob("*"))

            file_paths = []
            skipped_files = 0

            for f in all_files:
                if f.is_file():
                    if self._should_process_file(f):
                        file_paths.append(f)
                    else:
                        skipped_files += 1

            logger.debug(f"Found {len(file_paths)} processable files, skipped {skipped_files} files")

            if not file_paths:
                logger.warning(f"No processable files found in {repository.source}")
                return True

            classified_files = self.file_classifier.classify_files(file_paths)
            repo_id = self._generate_repo_id(repository)
            total_files_processed = 0
            total_chunks_generated = 0

            small_medium_files = (
                classified_files[FileSize.SMALL] + classified_files[FileSize.MEDIUM]
            )
            if small_medium_files:
                processed, chunks = self._process_small_medium_files(
                    small_medium_files, repository, repo_id
                )
                total_files_processed += processed
                total_chunks_generated += chunks

            large_files = classified_files[FileSize.LARGE]
            if large_files:
                processed, chunks = self._process_large_files(
                    large_files, repository, repo_id
                )
                total_files_processed += processed
                total_chunks_generated += chunks

            xlarge_files = classified_files[FileSize.EXTRA_LARGE]
            if xlarge_files:
                processed, chunks = self._process_xlarge_files(
                    xlarge_files, repository, repo_id
                )
                total_files_processed += processed
                total_chunks_generated += chunks

            self.batch_writer.update_repository_metadata(
                repo_id, repository, total_files_processed, total_chunks_generated
            )

            processing_time = time.time() - start_time
            logger.info(
                f"Completed adaptive processing for {repository.source}: "
                f"{total_files_processed} files, {total_chunks_generated} chunks "
                f"in {processing_time:.2f}s"
            )

            return True

        except Exception as e:
            logger.error(
                f"Error in adaptive processing for {repository.source}: {e}"
            )
            return False

    def _should_process_file(self, file_path: Path) -> bool:
        try:
            if any(part in self.skip_directories for part in file_path.parts):
                return False

            if file_path.suffix.lower() in self.binary_extensions:
                return False

            if file_path.name.lower() in self.skip_file_patterns:
                return False

            if file_path.name.startswith(".") and file_path.suffix not in {
                ".py", ".js",  ".ts", ".java", ".cpp", ".c", ".h",
            }:
                return False

            # Skip very large files (>100MB) to avoid memory issues
            try:
                file_size = file_path.stat().st_size
                if file_size > 100 * 1024 * 1024:  # 100MB
                    logger.debug(
                        f"Skipping large file: {file_path} ({file_size / 1024 / 1024:.1f}MB)"
                    )
                    return False

                if file_size == 0:
                    return False

            except OSError:
                return False

            try:
                with open(file_path, "rb") as f:
                    chunk = f.read(1024)  # Read first 1KB
                    if chunk:
                        if b"\x00" in chunk:
                            return False

                        printable_chars = sum(
                            1
                            for byte in chunk
                            if 32 <= byte <= 126 or byte in [9, 10, 13]
                        )
                        if len(chunk) > 0 and printable_chars / len(chunk) < 0.7:
                            return False
            except (IOError, OSError, PermissionError):
                return False
            return True
        except Exception as e:
            logger.debug(f"Error checking file {file_path}: {e}")
            return False

    def _process_small_medium_files(
        self,
        files: List[FileClassification],
        repository: RepositorySource,
        repo_id: str,
    ) -> Tuple[int, int]:
        logger.info(f"Processing {len(files)} small/medium files in batches")
        batches = self._create_memory_safe_batches(files)
        total_files = 0
        total_chunks = 0

        for i, batch in enumerate(batches):
            logger.debug(
                f"Processing batch {i + 1}/{len(batches)} with {len(batch)} files"
            )
            documents = []
            for file_class in batch:
                try:
                    doc = self._load_document(
                        file_class.path, Path(repository.source).name
                    )
                    if doc:
                        documents.append(doc)
                except UnicodeDecodeError as e:
                    logger.warning(f"Encoding error for {file_class.path}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error loading {file_class.path}: {e}")
                    continue

            if not documents:
                continue

            all_chunks = []
            for doc in documents:
                try:
                    doc_chunks = list(self.chunk_generator.process(doc))
                    all_chunks.extend(doc_chunks)
                except Exception as e:
                    logger.error(f"Error chunking document {doc.file_path}: {e}")
                    continue

            if not all_chunks:
                continue

            batch_embeddings = []
            batch_size = 50
            for i in range(0, len(all_chunks), batch_size):
                chunk_batch = all_chunks[i : i + batch_size]
                try:
                    embedding_batch = self.embedding_service.generate(chunk_batch)
                    batch_embeddings.extend(embedding_batch)
                except Exception as e:
                    logger.error(f"Error generating embeddings for batch: {e}")
                    continue

            try:
                self._write_batch_to_database(
                    documents, all_chunks, batch_embeddings, repo_id, repository.source
                )
                total_files += len(documents)
                total_chunks += len(all_chunks)
            except Exception as e:
                logger.error(f"Error writing batch to database: {e}")
                continue
            del documents, all_chunks, batch_embeddings
            gc.collect()
        return total_files, total_chunks

    @staticmethod
    def _load_document(file_path: Path, repo_name: str) -> Optional[Document]:
        try:
            from src.models.document_metadata import DocumentMetadata

            metadata = DocumentMetadata(
                doc_type=(
                    file_path.suffix.lstrip(".") if file_path.suffix else "unknown"
                ),
                file_size=file_path.stat().st_size,
                last_modified=file_path.stat().st_mtime,
            )
            content = None
            encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252", "ascii"]

            for encoding in encodings:
                try:
                    content = file_path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    break

            if content is None:
                logger.warning(f"Could not decode file with any encoding: {file_path}")
                return None

            # Skip files that are too short or seem corrupted
            if len(content.strip()) < 10:
                logger.debug(f"Skipping file with insufficient content: {file_path}")
                return None

            return Document.create(
                content=content,
                file_path=file_path,
                repo_name=repo_name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {e}")
            return None

    def _process_large_files(
        self,
        files: List[FileClassification],
        repository: RepositorySource,
        repo_id: str,
    ) -> Tuple[int, int]:
        logger.info(f"Processing {len(files)} large files individually with streaming")

        total_files = 0
        total_chunks = 0

        for file_class in files:
            try:
                logger.debug(
                    f"Streaming process: {file_class.path} ({file_class.size_bytes / 1024 / 1024:.1f}MB)"
                )
                chunks_processed = self._stream_process_file(
                    file_class.path,
                    Path(repository.source).name,
                    repo_id,
                    repository.source,
                )

                if chunks_processed > 0:
                    total_files += 1
                    total_chunks += chunks_processed

                # Force cleanup after each large file
                gc.collect()

            except Exception as e:
                logger.error(f"Error processing large file {file_class.path}: {e}")
                continue

        return total_files, total_chunks

    def _process_xlarge_files(
        self,
        files: List[FileClassification],
        repository: RepositorySource,
        repo_id: str,
    ) -> Tuple[int, int]:
        logger.info(
            f"Processing {len(files)} extra large files with advanced streaming"
        )

        total_files = 0
        total_chunks = 0

        for file_class in files:
            try:
                logger.info(
                    f"Advanced streaming: {file_class.path} ({file_class.size_bytes / 1024 / 1024:.1f}MB)"
                )
                chunks_processed = self._advanced_stream_process_file(
                    file_class.path,
                    Path(repository.source).name,
                    repo_id,
                    repository.source,
                )

                if chunks_processed > 0:
                    total_files += 1
                    total_chunks += chunks_processed

                # Aggressive cleanup after each extra large file
                gc.collect()
            except Exception as e:
                logger.error(
                    f"Error processing extra large file {file_class.path}: {e}"
                )
                continue

        return total_files, total_chunks

    def _create_memory_safe_batches(
        self, files: List[FileClassification]
    ) -> List[List[FileClassification]]:
        batches = []
        current_batch = []
        current_memory = 0
        sorted_files = sorted(files, key=lambda f: f.size_bytes)

        for file in sorted_files:
            if (
                current_memory + file.memory_requirement_mb
                > self.file_classifier.safe_memory_threshold * 1024
                and current_batch
            ):
                batches.append(current_batch)
                current_batch = [file]
                current_memory = file.memory_requirement_mb
            else:
                current_batch.append(file)
                current_memory += file.memory_requirement_mb

        if current_batch:
            batches.append(current_batch)

        return batches

    def _stream_process_file(
        self, file_path: Path, repo_name: str, repo_id: str, repo_source: str
    ) -> int:
        chunks_written = 0
        file_content_chunks = list(self.streaming_reader.read_file_chunks(file_path))

        if not file_content_chunks:
            return 0

        full_content = ""
        for chunk in file_content_chunks:
            full_content += chunk

        doc = self._create_document_from_content(full_content, file_path, repo_name)
        if not doc:
            return 0
        self.batch_writer.write_documents_to_sqlite([doc], repo_id)
        doc_chunks = list(self.chunk_generator.process(doc))
        embedding_batch_size = 50  # Smaller batches for large files
        for i in range(0, len(doc_chunks), embedding_batch_size):
            batch_chunks = doc_chunks[i : i + embedding_batch_size]
            batch_embeddings = self.embedding_service.generate(batch_chunks)
            self.batch_writer.write_chunks_to_sqlite(batch_chunks, repo_id)
            self.batch_writer.write_embeddings_to_qdrant(
                batch_embeddings, repo_id, repo_source
            )
            chunks_written += len(batch_chunks)
            del batch_chunks, batch_embeddings
            gc.collect()
        return chunks_written

    def _advanced_stream_process_file(
        self, file_path: Path, repo_name: str, repo_id: str, repo_source: str
    ) -> int:
        try:
            content = self.streaming_reader.read_file_with_mmap(file_path)
            if not content:
                return 0
            doc = self._create_document_from_content(content, file_path, repo_name)
            if not doc:
                return 0
            self.batch_writer.write_documents_to_sqlite([doc], repo_id)
            chunks_written = 0
            chunk_batch_size = 25  # Very small batches for extra large files
            chunk_iterator = self.chunk_generator.process(doc)

            batch_chunks = []
            for chunk in chunk_iterator:
                batch_chunks.append(chunk)
                if len(batch_chunks) >= chunk_batch_size:
                    batch_embeddings = self.embedding_service.generate(batch_chunks)
                    self.batch_writer.write_chunks_to_sqlite(batch_chunks, repo_id)
                    self.batch_writer.write_embeddings_to_qdrant(
                        batch_embeddings, repo_id, repo_source
                    )
                    chunks_written += len(batch_chunks)
                    del batch_chunks, batch_embeddings
                    batch_chunks = []
                    gc.collect()

            if batch_chunks:
                batch_embeddings = self.embedding_service.generate(batch_chunks)
                self.batch_writer.write_chunks_to_sqlite(batch_chunks, repo_id)
                self.batch_writer.write_embeddings_to_qdrant(
                    batch_embeddings, repo_id, repo_source
                )
                chunks_written += len(batch_chunks)
            return chunks_written
        except Exception as e:
            logger.error(f"Advanced streaming failed for {file_path}: {e}")
            return 0

    @staticmethod
    def _create_document_from_content(
        content: str, file_path: Path, repo_name: str
    ) -> Optional[Document]:
        try:
            from src.models.document_metadata import DocumentMetadata

            metadata = DocumentMetadata(
                doc_type=(
                    file_path.suffix.lstrip(".") if file_path.suffix else "unknown"
                ),
                file_size=len(content.encode()),
                last_modified=file_path.stat().st_mtime,
            )

            return Document.create(
                content=content,
                file_path=file_path,
                repo_name=repo_name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error creating document from content: {e}")
            return None

    def _process_document_batch(
        self, documents: List[Document]
    ) -> Tuple[List[Chunk], List[Embedding]]:
        all_chunks = []
        for doc in documents:
            doc_chunks = list(self.chunk_generator.process(doc))
            all_chunks.extend(doc_chunks)

        embeddings = self.embedding_service.generate(all_chunks) if all_chunks else []
        return all_chunks, embeddings

    def _write_batch_to_database(
        self,
        documents: List[Document],
        chunks: List[Chunk],
        embeddings: List[Embedding],
        repo_id: str,
        repo_source: str = "",
    ):
        try:
            if documents:
                self.batch_writer.write_documents_to_sqlite(documents, repo_id)

            if chunks:
                self.batch_writer.write_chunks_to_sqlite(chunks, repo_id)

            if embeddings:
                try:
                    logger.debug(
                        f"Starting Qdrant write for {len(embeddings)} embeddings"
                    )
                    self.batch_writer.write_embeddings_to_qdrant(
                        embeddings, repo_id, repo_source
                    )
                    logger.debug(
                        f"Completed Qdrant write for {len(embeddings)} embeddings"
                    )
                except Exception as qdrant_error:
                    logger.error(f"Qdrant write failed, but continuing: {qdrant_error}")
        except Exception as e:
            logger.error(f"Error writing batch to database: {e}")
            raise e

    @staticmethod
    def _generate_repo_id(repository: RepositorySource) -> str:
        source_hash = hashlib.md5(repository.source.encode()).hexdigest()[:12]
        return f"repo_{source_hash}"
