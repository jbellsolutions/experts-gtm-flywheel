from __future__ import annotations

import os


def get_secret(key: str) -> str:
    """Retrieve a secret from env (dev) or AWS SSM / HashiCorp Vault (prod)."""
    env = os.getenv("ENVIRONMENT", "development")

    value = os.getenv(key)
    if value:
        return value

    if env == "production":
        return _get_from_ssm(key)

    raise RuntimeError(f"Secret '{key}' not found. Add it to your .env file.")


def _get_from_ssm(key: str) -> str:
    """Fetch from AWS SSM Parameter Store."""
    import boto3
    ssm = boto3.client("ssm")
    param_name = f"/agentstack/{key.lower()}"
    response = ssm.get_parameter(Name=param_name, WithDecryption=True)
    return response["Parameter"]["Value"]
