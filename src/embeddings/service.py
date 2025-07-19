#!/usr/bin/env python3

import os
import logging
from typing import List
from src.models.chunk import Chunk
from src.models.embedding import Embedding
from langchain_ollama import OllamaEmbeddings
from src.core.configuration import ConfigLoader


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


class EmbeddingService:
    config: ConfigLoader = ConfigLoader()

    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model=self.config.get("embedding.model") or "nomic-embed-text:latest",
            num_gpu=self.config.get("embedding.num_gpu_layers") or 20,
        )
        self.batch_size = self.config.get("processing.batch_size") or 128
        self.model_name = (
            self.config.get("embedding.model") or "nomic-embed-text:latest"
        )
        self.embedding_dim = self._detect_embedding_dimension()
        logger.info(f"Embedding service initialized: {self.model_name} (dim: {self.embedding_dim})")

    def _detect_embedding_dimension(self) -> int:
        try:
            sample_vector = self.embeddings.embed_documents(["test"])[0]
            if hasattr(sample_vector, "__len__"):
                detected_dim = len(sample_vector)
                logger.debug(f"Detected embedding dimension: {detected_dim}")
                return detected_dim
            else:
                logger.warning(
                    "Could not detect embedding dimension, using default 768"
                )
                return 768
        except Exception as e:
            logger.warning(
                f"Error detecting embedding dimension: {e}, using default 768"
            )
            return 768

    def generate(self, chunks: List[Chunk]) -> List[Embedding]:
        if not chunks:
            return []

        try:
            texts = [chunk.content for chunk in chunks]
            logger.debug(f"Generating embeddings for {len(texts)} chunks using LangChain (batch)")
            vectors = self.embeddings.embed_documents(texts)
            if not vectors:
                logger.error("No vectors returned from LangChain embedding service")
                return []

            if vectors and len(vectors) > 0:
                sample_vector = vectors[0]
                logger.debug(f"Sample vector type: {type(sample_vector)}, "
                             f"length: {len(sample_vector) if hasattr(sample_vector, '__len__') else 'N/A'}"
                )
                if hasattr(sample_vector, "__iter__") and len(sample_vector) > 0:
                    logger.debug(f"First element type: {type(sample_vector[0])}")

            if len(vectors) != len(chunks):
                logger.error(
                    f"Dimension mismatch: {len(vectors)} vectors for {len(chunks)} chunks"
                )
                return []

            result_embeddings = []
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                try:
                    # Enhanced vector validation and conversion
                    processed_vector = self._process_vector(vector, i)

                    if processed_vector is None:
                        logger.warning(
                            f"Skipping invalid vector for chunk {chunk.chunk_hash}"
                        )
                        continue

                    if len(processed_vector) != self.embedding_dim:
                        logger.warning(
                            f"Vector dimension mismatch for chunk {chunk.chunk_hash}: "
                            f"got {len(processed_vector)}, expected {self.embedding_dim}"
                        )
                        continue

                    embedding = Embedding(
                        vector=processed_vector,
                        chunk_id=f"{chunk.doc_id}:{chunk.chunk_hash}",
                        model_name=self.model_name,
                        size=len(processed_vector),
                    )
                    result_embeddings.append(embedding)

                except Exception as e:
                    logger.error(
                        f"Error creating embedding for chunk {chunk.chunk_hash}: {e}"
                    )
                    continue

            logger.debug(
                f"Successfully created {len(result_embeddings)}/{len(chunks)} embeddings"
            )
            return result_embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    @staticmethod
    def _process_vector(vector, index: int) -> List[float] | None:
        try:
            if hasattr(vector, "tolist"):
                vector = vector.tolist()
            elif not isinstance(vector, list):
                vector = list(vector)

            if not vector or len(vector) == 0:
                logger.warning(f"Empty vector at index {index}")
                return None

            processed_vector = []
            for j, val in enumerate(vector):
                try:
                    float_val = float(val)

                    if not (float_val == float_val):  # NaN check
                        logger.warning(f"NaN value at vector[{index}][{j}]")
                        return None

                    if float_val == float("inf") or float_val == float("-inf"):
                        logger.warning(f"Infinite value at vector[{index}][{j}]")
                        return None

                    processed_vector.append(float_val)

                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid value at vector[{index}][{j}]: {val} - {e}"
                    )
                    return None
            return processed_vector
        except Exception as e:
            logger.error(f"Error processing vector at index {index}: {e}")
            return None

    def generate_single(self, text: str) -> List[float] | None:
        try:
            vector = self.embeddings.embed_documents([text])[0]
            return self._process_vector(vector, 0)
        except Exception as e:
            logger.error(f"Error generating single embedding: {e}")
            return None

    def get_embedding_dimension(self) -> int:
        return self.embedding_dim

    def health_check(self) -> bool:
        try:
            test_embedding = self.generate_single("test")
            if test_embedding and len(test_embedding) == self.embedding_dim:
                logger.debug("Embedding service health check passed")
                return True
            else:
                logger.error("Embedding service health check failed")
                return False
        except Exception as e:
            logger.error(f"Embedding service health check error: {e}")
            return False
