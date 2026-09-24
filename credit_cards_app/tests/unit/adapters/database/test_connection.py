def test_build_resource_creates_a_dynamodb_resource():
    from adapters.database.connection import build_resource

    resource = build_resource("us-east-1")
    assert resource.meta.client.__class__.__name__ == "DynamoDB"


def test_get_resource_returns_a_singleton():
    from adapters.database import connection

    first = connection.get_resource()
    second = connection.get_resource()
    assert first is second


def test_check_dynamodb_connection_is_true_for_an_active_table(
    dynamodb_resource,
):
    from adapters.database.connection import check_dynamodb_connection

    assert (
        check_dynamodb_connection(
            resource=dynamodb_resource, table_name="test_credit_cards"
        )
        is True
    )


def test_check_dynamodb_connection_is_false_for_a_missing_table(
    dynamodb_resource,
):
    from adapters.database.connection import check_dynamodb_connection

    assert (
        check_dynamodb_connection(
            resource=dynamodb_resource, table_name="does_not_exist"
        )
        is False
    )


def test_reset_resource_for_tests_drops_the_singleton():
    from adapters.database import connection

    connection.get_resource()
    connection.reset_resource_for_tests()
    assert connection._resource is None
    assert connection.get_resource() is not None
