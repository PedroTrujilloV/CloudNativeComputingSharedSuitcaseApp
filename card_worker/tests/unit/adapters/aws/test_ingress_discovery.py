"""Unit tests of the runtime discovery of the ingress load balancer."""

import pytest

from adapters.aws import ingress_discovery
from errors import TrueNativePollingError

INGRESS_TAG = {
    "kubernetes.io/cluster": "grupo33-dann-cluster",
    "kubernetes.io/service-name": "ingress-nginx/ingress-nginx-controller",
}


class FakeElbClient:
    """In-memory ELBv1 client with the two operations the discovery uses.

    A balancer without tags produces no ``TagDescriptions`` entry, as the
    real ELBv1 API does.
    """

    def __init__(self, load_balancers: list[dict]):
        self._load_balancers = load_balancers

    def describe_load_balancers(self) -> dict:
        return {
            "LoadBalancerDescriptions": [
                {
                    "LoadBalancerName": lb["name"],
                    "DNSName": lb["dns"],
                }
                for lb in self._load_balancers
            ]
        }

    def describe_tags(self, LoadBalancerNames: list[str]) -> dict:  # noqa: N803
        by_name = {lb["name"]: lb for lb in self._load_balancers}
        assert set(LoadBalancerNames) <= set(by_name)
        return {
            "TagDescriptions": [
                {
                    "LoadBalancerName": name,
                    "Tags": [
                        {"Key": key, "Value": value}
                        for key, value in by_name[name]["tags"].items()
                    ],
                }
                for name in LoadBalancerNames
                if by_name[name]["tags"]
            ]
        }


def factory(load_balancers: list[dict]):
    def _factory(region: str) -> FakeElbClient:  # noqa: ARG001
        return FakeElbClient(load_balancers)

    return _factory


def test_finds_the_ingress_balancer_among_others():
    load_balancers = [
        {
            "name": "some-other-elb",
            "dns": "some-other.example.com",
            "tags": {"kubernetes.io/cluster": "owned"},
        },
        {
            "name": "elb-0f1e2d3c4b",
            "dns": "elb-0f1e2d3c4b.us-east-1.elb.amazonaws.com",
            "tags": dict(INGRESS_TAG),
        },
    ]
    url = ingress_discovery.discover_truenative_base_url(
        client_factory=factory(load_balancers)
    )
    assert url == "https://elb-0f1e2d3c4b.us-east-1.elb.amazonaws.com"


def test_raises_when_there_is_no_load_balancer():
    with pytest.raises(TrueNativePollingError):
        ingress_discovery.discover_truenative_base_url(client_factory=factory([]))


def test_raises_when_no_balancer_matches_the_ingress_tag():
    load_balancers = [
        {"name": "elb-a", "dns": "a.example.com", "tags": {}},
        {
            "name": "elb-b",
            "dns": "b.example.com",
            "tags": {"kubernetes.io/service-name": "other/svc"},
        },
    ]
    with pytest.raises(TrueNativePollingError):
        ingress_discovery.discover_truenative_base_url(
            client_factory=factory(load_balancers)
        )
