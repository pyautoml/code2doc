#!/usr/bin/env python3

import os
import sqlite3
import hashlib
import logging
from pathlib import Path
from threading import Lock
from src.models.chunk import Chunk
from src.models.document import Document
from src.models.embedding import Embedding
from typing import Dict, Any, List, Optional
from src.core.configuration import ConfigLoader
from src.models.repository import RepositorySource


logger: logging.Logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
    )
except ImportError:
    raise ImportError("Qdrant not installed. Install with: pip install qdrant-client")


class QdrantBatchWriter:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantBatchWriter, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if QdrantBatchWriter._initialized:
            return

        self.config = ConfigLoader()
        self.sqlite_lock = Lock()
        self.qdrant_lock = Lock()

        base_dir = Path.cwd()
        self.sqlite_db_path = str(
            base_dir
            / self.config.get("database.sqlite_path", "storage/database/files.db")
        )
        self.qdrant_db_path = str(
            base_dir
            / self.config.get("database.qdrant_path", "storage/database/qdrant")
        )

        Path(self.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.qdrant_db_path).mkdir(parents=True, exist_ok=True)

        logger.info(f"Database paths - SQLite: {self.sqlite_db_path}, Qdrant: {self.qdrant_db_path}")

        self._init_qdrant_collection()
        self._init_sqlite_tables()
        QdrantBatchWriter._initialized = True

    def _init_sqlite_tables(self):
        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    conn.execute(
                    """
                        CREATE TABLE IF NOT EXISTS repositories
                          (
                             id           TEXT PRIMARY KEY,
                             source       TEXT NOT NULL,
                             type         TEXT NOT NULL,
                             total_files  INTEGER DEFAULT 0,
                             total_chunks INTEGER DEFAULT 0,
                             content_hash TEXT,
                             processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                          ); 
                    """
                    )

                    try:
                        conn.execute(
                            "ALTER TABLE repositories ADD COLUMN content_hash TEXT"
                        )
                    except sqlite3.OperationalError:
                        pass
                    conn.commit()
                    logger.debug("SQLite tables initialized with repository hash tracking")
                except Exception as e:
                    logger.error(f"Error initializing SQLite tables: {e}")

    def _init_qdrant_collection(self):
        try:
            logger.info("Initializing local Qdrant...")
            self.qdrant_client = QdrantClient(path=self.qdrant_db_path)
            self.collection_name = "documents"
            # Get embedding dimension from config or default
            embedding_dim = self.config.get("embedding.embedding_dim", 768)
            # Check if collection exists
            try:
                collection_info = self.qdrant_client.get_collection(self.collection_name)
                logger.debug(f"Found existing Qdrant collection: {collection_info}")
            except Exception:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=embedding_dim, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created new Qdrant collection: {self.collection_name} (dim: {embedding_dim})")
            logger.info("Qdrant initialized successfully")
        except Exception as e:
            self.qdrant_client = None
            self.collection_name = None
            raise Exception(f"Error initializing Qdrant: {e}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def delete_repository_data(self, repo_id: str):
        logger.info(f"Deleting all data for repository: {repo_id}")

        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM documents WHERE repo_id = ?", (repo_id,))

                    cursor.execute("DELETE FROM chunks WHERE repo_id = ?", (repo_id,))
                    chunks_deleted = cursor.rowcount

                    cursor.execute("DELETE FROM documents WHERE repo_id = ?", (repo_id,))
                    docs_deleted = cursor.rowcount

                    cursor.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
                    repo_deleted = cursor.rowcount

                    conn.commit()
                    logger.debug(f"SQLite cleanup: {repo_deleted} repo, {docs_deleted} docs, {chunks_deleted} chunks")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error deleting repository data from SQLite: {e}")
                    raise e

        if self.qdrant_client and self.collection_name:
            with self.qdrant_lock:
                try:
                    filter_condition = Filter(
                        must=[
                            FieldCondition(
                                key="repo_id", match=MatchValue(value=repo_id)
                            )
                        ]
                    )
                    self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=filter_condition,
                    )
                    logger.debug(f"Deleted Qdrant vectors for repository: {repo_id}")
                except Exception as e:
                    logger.error(f"Error deleting repository data from Qdrant: {e}")

    def get_existing_repository_sources(self, sources: List[str]) -> List[str]:
        with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(sources))
            cursor.execute(f"SELECT source FROM repositories WHERE source IN ({placeholders})",sources,)
            existing = [row[0] for row in cursor.fetchall()]
            return existing

    def get_repository_hash(self, repo_id: str) -> Optional[str]:
        with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content_hash FROM repositories WHERE id = ?", (repo_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def store_repository_hash(self, repo_id: str, content_hash: str):
        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    conn.execute(
                """
                    UPDATE repositories
                    SET    content_hash = ?,
                           processed_at = CURRENT_TIMESTAMP
                    WHERE  id = ? 
                    """,(content_hash, repo_id),
                    )
                    conn.commit()
                    logger.debug(f"Updated repository hash for {repo_id}")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error storing repository hash: {e}")
                    raise e

    def write_repository_batch(self, batch) -> bool:
        if not batch.documents:
            logger.warning(f"No data to write for repository: {batch.repository.source}")
            return True
        try:
            repo_id = self._generate_repo_id(batch.repository)
            self._write_sqlite_batch(batch, repo_id)
            if self.qdrant_client and batch.embeddings:
                self._write_qdrant_batch(batch, repo_id)

            logger.info(
                f"Successfully wrote repository batch: {batch.repository.source} "
                f"(Files: {batch.total_files}, Chunks: {batch.total_chunks})"
            )
            return True
        except Exception as e:
            logger.error(f"Error writing repository batch {batch.repository.source}: {e}")
            return False

    def write_documents_to_sqlite(self, documents: List[Document], repo_id: str):
        if not documents:
            return

        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    document_data = []
                    for doc in documents:
                        if not doc.file_hash:
                            logger.error(
                                f"Document {doc.file_path} has empty file_hash"
                            )
                            continue

                        document_data.append(
                            (
                                doc.doc_uuid,
                                repo_id,
                                str(doc.file_path),
                                doc.file_hash,
                                (
                                    doc.content[:500] + "..."
                                    if len(doc.content) > 500
                                    else doc.content
                                ),
                            )
                        )

                    if document_data:
                        conn.executemany(
                    """
                            INSERT OR REPLACE INTO documents 
                            (id, repo_id, file_path, file_hash, content_preview) 
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            document_data,
                        )
                        conn.commit()
                        logger.debug(f"Wrote {len(document_data)} documents to SQLite")

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error writing documents to SQLite: {e}")
                    raise e

    def write_chunks_to_sqlite(self, chunks: List[Chunk], repo_id: str):
        if not chunks:
            return

        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    chunk_data = [
                        (
                            f"{chunk.doc_id}:{chunk.chunk_hash}",
                            chunk.doc_id,
                            repo_id,
                            chunk.chunk_hash,
                            chunk.content,
                            str(chunk.metadata) if chunk.metadata else "",
                        )
                        for chunk in chunks
                    ]

                    conn.executemany(
                """
                        INSERT OR REPLACE INTO chunks 
                        (id, doc_id, repo_id, chunk_hash, content, metadata) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        chunk_data,
                    )
                    conn.commit()
                    logger.debug(f"Wrote {len(chunk_data)} chunks to SQLite")

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error writing chunks to SQLite: {e}")
                    raise e

    def write_embeddings_to_qdrant(
        self, embeddings: List[Embedding], repo_id: str, repo_source: str = ""
    ):
        if not embeddings or not self.qdrant_client:
            if not self.qdrant_client:
                logger.debug("Qdrant not available, skipping vector storage")
            return

        with self.qdrant_lock:
            try:
                valid_embeddings = []
                for emb in embeddings:
                    if (
                        emb.vector
                        and isinstance(emb.vector, list)
                        and len(emb.vector) > 0
                        and emb.chunk_id
                    ):
                        valid_embeddings.append(emb)

                if not valid_embeddings:
                    logger.warning("No valid embeddings for Qdrant")
                    return

                points = []
                for i, emb in enumerate(valid_embeddings):
                    try:
                        point_id = abs(hash(f"{repo_id}_{emb.chunk_id}")) % (2**31)
                        point = PointStruct(
                            id=point_id,
                            vector=emb.vector,
                            payload={
                                "chunk_id": emb.chunk_id,
                                "repo_id": repo_id,
                                "repo_source": repo_source,
                                "model": getattr(emb, "model_name", "unknown"),
                                "chunk_size": getattr(emb, "size", len(emb.vector)),
                            },
                        )
                        points.append(point)
                    except Exception as e:
                        logger.error(f"Error preparing point for embedding {i}: {e}")
                        continue

                if points:
                    batch_size = 100
                    successful_batches = 0
                    for i in range(0, len(points), batch_size):
                        batch_points = points[i : i + batch_size]
                        try:
                            self.qdrant_client.upsert(
                                collection_name=self.collection_name,
                                points=batch_points,
                            )
                            successful_batches += 1
                            logger.debug(
                                f"Wrote Qdrant batch {i // batch_size + 1} ({len(batch_points)} vectors)"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error writing Qdrant batch {i // batch_size + 1}: {e}"
                            )
                            continue
                logger.info(f"Successfully wrote {len(points)} vectors to Qdrant ({successful_batches} batches)")
            except Exception as e:
                logger.error(f"Error writing to Qdrant: {e}")

    def _write_sqlite_batch(self, batch, repo_id: str):
        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    conn.execute(
                """
                        INSERT OR REPLACE INTO repositories 
                        (id, source, type, total_files, total_chunks) 
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            repo_id,
                            batch.repository.source,
                            batch.repository.type,
                            batch.total_files,
                            batch.total_chunks,
                        ),
                    )

                    if batch.documents:
                        document_data = [
                            (
                                doc.doc_uuid,
                                repo_id,
                                str(doc.file_path),
                                doc.file_hash,
                                (
                                    doc.content[:500] + "..."
                                    if len(doc.content) > 500
                                    else doc.content
                                ),
                            )
                            for doc in batch.documents
                            if doc.file_hash
                        ]

                        if document_data:
                            conn.executemany(
                        """
                                INSERT OR REPLACE INTO documents 
                                (id, repo_id, file_path, file_hash, content_preview) 
                                VALUES (?, ?, ?, ?, ?)
                            """,
                                document_data,
                            )

                    if batch.chunks:
                        chunk_data = [
                            (
                                f"{chunk.doc_id}:{chunk.chunk_hash}",
                                chunk.doc_id,
                                repo_id,
                                chunk.chunk_hash,
                                chunk.content,
                                str(chunk.metadata) if chunk.metadata else "",
                            )
                            for chunk in batch.chunks
                        ]

                        conn.executemany(
                    """
                            INSERT OR REPLACE INTO chunks 
                            (id, doc_id, repo_id, chunk_hash, content, metadata) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """,
                            chunk_data,
                        )
                    conn.commit()
                    logger.debug(f"SQLite batch write completed for {repo_id}")
                except Exception as e:
                    conn.rollback()
                    raise e

    def _write_qdrant_batch(self, batch, repo_id: str):
        if batch.embeddings:
            self.write_embeddings_to_qdrant(
                batch.embeddings, repo_id, batch.repository.source
            )

    def update_repository_metadata(
        self,
        repo_id: str,
        repository: RepositorySource,
        total_files: int,
        total_chunks: int,
    ):
        with self.sqlite_lock:
            with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
                try:
                    conn.execute(
                """
                        INSERT OR REPLACE INTO repositories 
                        (id, source, type, total_files, total_chunks) 
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            repo_id,
                            repository.source,
                            repository.type,
                            total_files,
                            total_chunks,
                        ),
                    )
                    conn.commit()
                    logger.debug(f"Updated repository metadata for {repo_id}")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error updating repository metadata: {e}")
                    raise e

    @staticmethod
    def _generate_repo_id(repository: RepositorySource) -> str:
        source_hash = hashlib.md5(repository.source.encode()).hexdigest()[:12]
        return f"repo_{source_hash}"

    def get_repository_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM repositories")
            total_repos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM chunks")
            total_chunks = cursor.fetchone()[0]
            cursor.execute(
            """
                SELECT source, total_files, total_chunks, processed_at
                FROM repositories
                ORDER BY processed_at DESC
            """
            )
            repo_stats = cursor.fetchall()
            qdrant_vectors = 0
            if self.qdrant_client:
                try:
                    collection_info = self.qdrant_client.get_collection(
                        self.collection_name
                    )
                    qdrant_vectors = collection_info.vectors_count or 0
                except:
                    pass

            return {
                "total_repositories": total_repos,
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "total_vectors": qdrant_vectors,
                "repositories": [
                    {
                        "source": row[0],
                        "files": row[1],
                        "chunks": row[2],
                        "processed_at": row[3],
                    }
                    for row in repo_stats
                ],
            }
