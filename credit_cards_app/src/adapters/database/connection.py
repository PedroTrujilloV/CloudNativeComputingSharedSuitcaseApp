"""
DynamoDB resource management for the Credit Cards application.

The table is provisioned by the 3_dynamodb Terraform stack and is exclusive
to this application. Credentials are resolved by the standard boto3 chain
(environment variables, instance or pod role); nothing is hardcoded here.
"""

import boto3
from botocore.exceptions import ClientError

from config import Settings

# A boto3 DynamoDB resource (the boto3.resource factory returns it lazily,
# so the annotation stays as a plain comment rather than a runtime type).
_resource = None


def build_resource(region_name: str | None = None):
    """Create a DynamoDB boto3 resource for the configured region."""
    return boto3.resource("dynamodb", region_name=region_name or Settings.aws_region)


def get_resource():
    """Return the process-wide DynamoDB resource (singleton)."""
    global _resource
    if _resource is None:
        _resource = build_resource()
    return _resource


def check_dynamodb_connection(
    resource=None,
    table_name: str | None = None,
) -> bool:
    """Return True when the configured table exists and is ACTIVE.

    Any failure to describe the table (missing table, denied credentials,
    unreachable endpoint) is reported as False so the probe can be used as
    a plain connectivity check.
    """
    active_resource = resource or get_resource()
    table = active_resource.Table(table_name or Settings.dynamodb_table_name)
    try:
        table.load()
    except ClientError:
        return False
    return table.table_status == "ACTIVE"


def reset_resource_for_tests() -> None:
    """Drop the singleton resource (unit tests only)."""
    global _resource
    _resource = None
