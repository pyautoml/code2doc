#!/usr/bin/env python3
import os
import logging
import warnings
from pathlib import Path
from src.system.logger import LoggerConfig
from src.core.configuration import ConfigLoader
from src.system.environment import setup_env_variables
from src.core.processes.ollama_and_models import start_ollama_models

try:
    import transformers
    import huggingface_hub
except ImportError as e:
    if "DLL load failed" in str(e):
        pass

os.environ["DISABLE_WARNINGS"] = "1"
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


class Bootstrap:
    config: ConfigLoader = ConfigLoader()
    logger: logging.Logger = LoggerConfig(
        use=config.get("app.logging", True),
        name=config.get("app.logger_name", "Code2Doc"),
        level=config.get("app.logging_level", "INFO"),
    ).get()

    os.environ["LOGGER"] = config.get("app.logger_name", "Code2Doc")

    @classmethod
    def run(cls):
        cls.logger.info("Running app configuration.")
        cls._setup_environment()
        cls._application_directories()
        cls._database_setup()
        cls._initialize_ollama_models()

    @classmethod
    def _setup_environment(cls):
        cls.logger.debug("Setting up CUDA environment.")
        setup_env_variables(cls.config.get("cuda"))

        cls.logger.debug("Setting up Huggingface environment.")
        setup_env_variables(cls.config.get("huggingface"))

    @classmethod
    def _application_directories(cls):
        cls.logger.debug("Creating application directories.")
        root: Path = Path.cwd() / Path("storage")
        os.makedirs(root, exist_ok=True)
        for dir_name in cls.config.get("app.directories", []):
            os.makedirs(root / Path(dir_name), exist_ok=True)

    @classmethod
    def _database_setup(cls):
        cls.logger.debug("Creating application database.")

        base_dir = Path.cwd()
        sqlite_path = base_dir / cls.config.get(
            "database.sqlite_path", "storage/database/files.db"
        )
        chroma_path = base_dir / cls.config.get(
            "database.chroma_path", "storage/database/chroma"
        )

        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        chroma_path.mkdir(parents=True, exist_ok=True)

        cls.logger.debug(f"SQLite database path: {sqlite_path}")
        cls.logger.debug(f"ChromaDB path: {chroma_path}")

        cls._init_sqlite_database(sqlite_path)

        os.environ["SQLITE_DB_PATH"] = str(sqlite_path)
        os.environ["CHROMA_DB_PATH"] = str(chroma_path)

    @classmethod
    def _init_sqlite_database(cls, db_path: Path):
        import sqlite3

        try:
            with sqlite3.connect(str(db_path), timeout=30) as conn:
                conn.executescript(
                """
                    CREATE TABLE IF NOT EXISTS repositories
                      (
                         id           TEXT PRIMARY KEY,
                         source       TEXT NOT NULL,
                         type         TEXT NOT NULL,
                         total_files  INTEGER DEFAULT 0,
                         total_chunks INTEGER DEFAULT 0,
                         processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                      );
                    
                    CREATE TABLE IF NOT EXISTS documents
                      (
                         id              TEXT PRIMARY KEY,
                         repo_id         TEXT NOT NULL,
                         file_path       TEXT NOT NULL,
                         file_hash       TEXT NOT NULL,
                         content_preview TEXT,
                         FOREIGN KEY ( repo_id ) REFERENCES repositories ( id )
                      );
                    
                    CREATE TABLE IF NOT EXISTS chunks
                      (
                         id         TEXT PRIMARY KEY,
                         doc_id     TEXT NOT NULL,
                         repo_id    TEXT NOT NULL,
                         chunk_hash TEXT NOT NULL,
                         content    TEXT NOT NULL,
                         metadata   TEXT,
                         FOREIGN KEY ( doc_id ) REFERENCES documents ( id ),
                         FOREIGN KEY ( repo_id ) REFERENCES repositories ( id )
                      );
                    
                    CREATE INDEX IF NOT EXISTS idx_chunks_repo ON chunks(repo_id);
                    
                    CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
                    
                    CREATE INDEX IF NOT EXISTS idx_documents_repo ON documents(repo_id); 
                """
                )
                cls.logger.info(f"SQLite database initialized at: {db_path}")
        except Exception as e:
            cls.logger.error(f"Error initializing SQLite database: {e}")

    @classmethod
    def _initialize_ollama_models(cls):
        cls.logger.debug("Initializing OLLAMA models.")
        os.environ["OLLAMA_HOST"] = cls.config.get(
            "ollama.host", "http://localhost:11434"
        )
        os.environ["OLLAMA_MODELS"] = cls.config.get("ollama.ollama_models_path", "")
        start_ollama_models(
            host=cls.config.get("ollama.host"),
            endpoint_tags=cls.config.get("ollama.endpoint_tags"),
            endpoint_pull=cls.config.get("ollama.endpoint_pull"),
            endpoint_generate=cls.config.get("ollama.endpoint_generate"),
            models=[
                cls.config.get("llm.writer_model"),
                cls.config.get("llm.reviewer_model"),
            ],
            embedding_model=cls.config.get("embedding.model"),
            proxy=None or cls.config.get("network.proxy"),
            headers=None or cls.config.get("network.headers"),
        )
