#!/usr/bin/env python3
import os
import json
import httpx
import asyncio
import logging
import subprocess
from typing import List, Optional, Union
from src.system.exceptions import OllamaRequestException, OllamaModelWarmupException


logger: logging.Logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


def model_size_to_timeout(model_name: str) -> int:
    model_lower = model_name.lower()
    if any(keyword in model_lower for keyword in ["vision", "llava", "minicpm"]):
        return 600  # 10 minutes
    if any(
        keyword in model_lower for keyword in ["70b", "72b", "8x7b", "8x22b", "mixtral"]
    ):
        return 900  # 15 minutes
    if any(
        keyword in model_lower
        for keyword in ["8b", "9b", "10b", "11b", "12b", "13b", "cogito"]
    ):
        return 480  # 8 minutes
    if any(keyword in model_lower for keyword in ["4b", "5b", "6b", "7b", "gemma3"]):
        return 240  # 4 minutes
    if any(keyword in model_lower for keyword in ["1b", "2b", "3b", "phi3"]):
        return 120  # 2 minutes
    return 240


def ollama_running(host: str) -> bool:
    logger.debug("Checking if Ollama is ON")
    try:
        with httpx.Client(timeout=2) as client:
            response = client.get(url=host)
            return response.status_code == 200
    except:
        return False


def ollama_on_host() -> bool:
    logger.debug("Checking if Ollama is installed on host")
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


async def make_request_with_retry(
    method: str,
    url: str,
    client: Optional[httpx.AsyncClient] = None,
    proxy: Optional[dict] = None,
    headers: Optional[dict] = None,
    retries: int = 3,
    timeout: Union[int, float] = 60,
) -> httpx.Response:
    last_exception = None
    if not client:
        client = httpx.AsyncClient(headers=headers, proxy=proxy, timeout=timeout)

    for attempt in range(retries):
        try:
            response = await client.request(method, url)
            response.raise_for_status()
            return response

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            last_exception = e

            if attempt < retries:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{retries + 1}), "
                )
                await asyncio.sleep(5)
            else:
                break
    raise OllamaRequestException(
        f"Request failed after {retries + 1} attempts"
    ) from last_exception


async def get_installed_models(
    endpoint_tags: str,
    proxy: Optional[dict] = None,
    headers: Optional[dict] = None,
    retries: int = 3,
) -> List[Optional[str]]:

    client = httpx.AsyncClient(headers=headers, proxy=proxy)

    try:
        response = await make_request_with_retry(
            method="GET",
            url=endpoint_tags,
            client=client,
            proxy=proxy,
            headers=headers,
            retries=retries,
            timeout=30,
        )
        models_data = response.json().get("models", [])
        models: List[str] = [model.get("name") for model in models_data if model]
        logger.debug(f"Installed models: {models}")
        return models
    except Exception as e:
        raise OllamaRequestException(f"Failed to get installed models: {e}") from e
    finally:
        await client.aclose()


async def download_model(
    model_name: str,
    endpoint_pull: str,
    client: Optional[httpx.AsyncClient] = None,
    proxy: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> None:
    own_client = False

    if client is None:
        client = httpx.AsyncClient(headers=headers, proxy=proxy)
        own_client = True
    try:
        payload = {"model": model_name}
        model_timeout: int = model_size_to_timeout(model_name)
        logger.debug(f"Model {model_name} - timeout set to {model_timeout} second(s)")

        async with client.stream(
            "POST", endpoint_pull, timeout=model_timeout, json=payload
        ) as response:
            if response.status_code != 200:
                raise OllamaRequestException(
                    f"Download failed for model {model_name} with status {response.status_code}"
                )
            async for chunk in response.aiter_text():
                if chunk.strip():
                    try:
                        progress_data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue  # Skip malformed JSON chunks
                    if progress_data.get("status") == "success":
                        logger.debug(f"Downloaded model {model_name}")
                        break
    except Exception as e:
        raise OllamaRequestException(
            f"Failed to download model {model_name}: {e}"
        ) from e
    finally:
        if own_client:
            await client.aclose()


async def download_missing_models(
    endpoint_pull: str,
    endpoint_tags: str,
    models: List[str],
    proxy: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> None:
    logger.debug(f"Requested models: {models}")
    installed_models: List[Optional[str]] = await get_installed_models(endpoint_tags)
    unique_models = [model for model in models if model not in installed_models]
    if not unique_models:
        logger.debug("All models are already installed.")
        return

    logger.debug(
        f"Requesting pulls for missing models: {','.join([u for u in unique_models])}"
    )
    async with httpx.AsyncClient(headers=headers, proxy=proxy) as client:
        tasks = [
            download_model(model_name, endpoint_pull, client=client)
            for model_name in unique_models
            if model_name
        ]
        await asyncio.gather(*tasks)

async def initialize_models(self, models: List[str]):
    try:
        # Remove duplicates while preserving order
        unique_models = []
        seen = set()
        for model in models:
            if model not in seen:
                unique_models.append(model)
                seen.add(model)

        if not unique_models:
            raise OllamaModelWarmupException("No generative models found to initialize")

        tasks = []
        for model_name in unique_models:
            model_size, timeout = self._get_model_size_and_timeout(model_name)
            self.logger.debug(
                f"Model {model_name} classified as {model_size.value} (timeout: {timeout}s)"
            )
            tasks.append(self._warm_model_task(model_name, timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        warm_success_count = sum(1 for r in results if r is True)
        warm_failed_count = sum(1 for r in results if r is not True)

        total_models = len(unique_models)
        if warm_success_count == total_models:
            self.logger.info(
                f"All {total_models} generative models successfully are loaded"
            )
        elif warm_success_count > 0:
            self.logger.warning(
                f"⚠️ Model warming completed: {warm_success_count}/{total_models} successful, "
                f"{warm_failed_count} failed"
            )
        else:
            raise OllamaModelWarmupException(
                f"Model warming failed: 0/{total_models} models warmed successfully"
            )
    except ImportError as e:
        raise OllamaModelWarmupException(
            f"Failed to import required modules for model warming: {e}"
        )
    except Exception as e:
        raise OllamaModelWarmupException(f"Model initialization failed: {e}")


async def warm_model_with_timeout_async(
    model_name: str, endpoint_generate: str, timeout: int = 300
) -> bool:
    try:
        payload = {
            "model": model_name,
            "prompt": "Hello, this is a test prompt to warm up the model.",
            "stream": False,
            "keep_alive": -1,
            "options": {
                "num_predict": 5,
                "temperature": 0.1,
            },
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await asyncio.wait_for(
                client.post(endpoint_generate, json=payload), timeout=timeout
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to warm up model {model_name}: HTTP {response.status_code}"
                )
                return False

            result = response.json()
            if not result.get("response"):
                logger.error(f"Empty response from model {model_name}")
                return False
            logger.debug(f"Successfully warmed up model: {model_name}")
            return True

    except asyncio.TimeoutError:
        logger.error(f"Timed out warming up model {model_name}")
        return False
    except Exception as e:
        logger.error(f"Error warming up model {model_name}: {e}")
        return False


def embedding_dimension(model_name: str, endpoint_embedding: str) -> Optional[int]:
    headers = {"Content-Type": "application/json"}
    payload = {"model": model_name, "prompt": "test data for dimension check"}
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.post(endpoint_embedding, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if "embedding" in data and data["embedding"]:
                    print(f"Success! Embedding dimension: {len(data['embedding'])}")
                    return len(data["embedding"])
        except Exception as e:
            raise OllamaRequestException(
                f"Failed to get embedding dimension: {e}"
            ) from e
