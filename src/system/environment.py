#!/usr/bin/env python3

import os

def setup_env_variables(env_variables: dict):
    for key, value in env_variables.items():
        os.environ[key] = str(value)
