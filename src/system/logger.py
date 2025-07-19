#!/usr/bin/env python3

import os
import sys
import logging
import coloredlogs
from typing import Any, Dict
from pydantic import BaseModel, Field, model_validator


class LoggerConfig(BaseModel):
    use: bool = Field(
        default=False, description="Whether to use this logger configuration"
    )
    name: str = Field(default="code2doc", min_length=1)
    level: str = Field(
        default="INFO",
        description="Logging level",
        examples=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    @classmethod
    @model_validator(mode="before")
    def validate_use(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if os.getenv("LOGGING_ENABLED", None):
            values["use"] = True
        return values

    @classmethod
    @model_validator(mode="before")
    def validate_log_level(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        level = values.get("level", "INFO")
        if isinstance(level, int):
            if level < 0 or level > 50:
                raise ValueError("Log level must be between 0 and 50")
            # Convert int back to string for consistency
            int_to_string = {
                50: "CRITICAL",
                40: "ERROR",
                30: "WARNING",
                20: "INFO",
                10: "DEBUG",
            }
            values["level"] = int_to_string.get(level, "INFO")
        else:
            # Validate string level
            level = level.upper()
            valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
            if level not in valid_levels:
                raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
            values["level"] = level
        return values

    model_config = {
        "extra": "forbid",
    }

    def _get_level_int(self) -> int:
        """Convert string level to integer for logging configuration."""
        levels = {"CRITICAL": 50, "ERROR": 40, "WARNING": 30, "INFO": 20, "DEBUG": 10}
        return levels.get(self.level.upper(), 20)

    def get(self) -> logging.Logger:
        if self.use:
            return self.__create()
        return self.__null_logger()

    @staticmethod
    def __null_logger(name: str = "null") -> logging.Logger:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    def __create(self) -> logging.Logger:
        logger = logging.getLogger(self.name)
        if logger.handlers:
            return logger

        level = self._get_level_int()
        logger.setLevel(level)
        formatter = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(formatter))
        logger.addHandler(console_handler)

        try:
            coloredlogs.install(
                level=level,
                logger=logger,
                fmt=formatter,
                datefmt="%Y-%m-%d %H:%M:%S",
                field_styles={
                    "asctime": {"color": "white"},
                    "hostname": {"color": "white"},
                    "levelname": {},
                    "filename": {"color": "white"},
                    "name": {"color": "blue"},
                    "lineno": {"color": "white"},
                    "message": {},
                },
                level_styles={
                    "DEBUG": {"color": "white"},
                    "INFO": {"color": "green"},
                    "WARNING": {"color": "yellow"},
                    "ERROR": {"color": "red"},
                    "CRITICAL": {"color": "red", "bold": True},
                },
            )
        except ImportError:
            pass
        return logger
