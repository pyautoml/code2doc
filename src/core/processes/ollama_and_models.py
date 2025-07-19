#!/usr/bin/env python3
import os
import logging
import asyncio
from typing import List, Optional
from src.system.exceptions import BootstrapException, OllamaModelWarmupException
from src.core.processes.ollama_requests import (
    ollama_on_host,
    ollama_running,
    download_missing_models,
    warm_model_with_timeout_async,
)


logger: logging.Logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


def _download_models(
    endpoint_pull: str,
    endpoint_tags: str,
    models: List[str],
    proxy: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> None:
    logger.debug("Downloading missing Ollama models")
    asyncio.run(
        download_missing_models(endpoint_pull, endpoint_tags, models, proxy, headers)
    )

async def _initialize_models(models: List[str], endpoint_generate: str) -> None:
    logger.debug("Warming up Ollama models")
    model_name = None
    unique_models: List[Optional[str]] = list(set(models))
    if not unique_models:
        raise OllamaModelWarmupException("No models to warm up.")
    try:
        tasks = [
            warm_model_with_timeout_async(model, endpoint_generate)
            for model in unique_models
        ]
        await asyncio.gather(*tasks)
    except Exception as e:
        raise OllamaModelWarmupException(f"Failed to warm model {model_name}: {e}")

def start_ollama_models(
    host: str,
    endpoint_tags: str,
    endpoint_pull: str,
    endpoint_generate: str,
    embedding_model: str,
    models: List[str],
    proxy: Optional[str] = None,
    headers: Optional[dict] = None,
) -> None:
    if not ollama_on_host():
        raise BootstrapException(
            "Ollama is not installed on the host or the host url is not correct."
        )
    if not ollama_running(host):
        raise BootstrapException("Ollama is installed but not running.")
    _download_models(
        host + endpoint_pull,
        host + endpoint_tags,
        models + [embedding_model],
        proxy,
        headers,
    )
    asyncio.run(_initialize_models(models, host + endpoint_generate))
