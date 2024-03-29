"""Prometheus helper class for generating scrape jobs for Volcano."""
from typing import List


class Prometheus:
    """Prometheus is a helper class for generating prometheus scrape jobs for Volcano.

    It is used by the Volcano charm to generate configuration files for
    the metrics_endpoint relation in COS lite.

    :param str namespace: The namespace where kube-state-metrics is deployed.
    """

    def __init__(self, namespace: str = "kube-system"):
        self.namespace = namespace

    @property
    def scrape_jobs(self) -> List[dict]:
        """Returns a list of scrape jobs for the Volcano charm."""
        return [
            {
                "job_name": "kubernetes-apiservers",
                "kubernetes_sd_configs": [{"role": "endpoints"}],
                "scheme": "https",
                "tls_config": {"ca_file": "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"},
                "bearer_token_file": "/var/run/secrets/kubernetes.io/serviceaccount/token",
                "relabel_configs": [
                    {
                        "source_labels": [
                            "__meta_kubernetes_namespace",
                            "__meta_kubernetes_service_name",
                            "__meta_kubernetes_endpoint_port_name",
                        ],
                        "action": "keep",
                        "regex": "default;kubernetes;https",
                    }
                ],
            },
            {
                "job_name": "kubernetes-nodes",
                "scheme": "https",
                "tls_config": {"ca_file": "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"},
                "bearer_token_file": "/var/run/secrets/kubernetes.io/serviceaccount/token",
                "kubernetes_sd_configs": [{"role": "node"}],
                "relabel_configs": [
                    {
                        "action": "labelmap",
                        "regex": "__meta_kubernetes_node_label_(.+)",
                    },
                    {"target_label": "__address__", "replacement": "kubernetes.default.svc:443"},
                    {
                        "source_labels": ["__meta_kubernetes_node_name"],
                        "regex": "(.+)",
                        "target_label": "__metrics_path__",
                        "replacement": "/api/v1/nodes/${1}/proxy/metrics",
                    },
                ],
            },
            {
                "job_name": "kubernetes-pods",
                "kubernetes_sd_configs": [{"role": "pod"}],
                "relabel_configs": [
                    {
                        "source_labels": ["__meta_kubernetes_pod_annotation_prometheus_io_scrape"],
                        "action": "keep",
                        "regex": "true",
                    },
                    {
                        "source_labels": ["__meta_kubernetes_pod_annotation_prometheus_io_path"],
                        "action": "replace",
                        "target_label": "__metrics_path__",
                        "regex": "(.+)",
                    },
                    {
                        "source_labels": [
                            "__address__",
                            "__meta_kubernetes_pod_annotation_prometheus_io_port",
                        ],
                        "action": "replace",
                        "regex": "([^:]+)(?::\d+)?;(\d+)",  # noqa: W605
                        "replacement": "$1:$2",
                        "target_label": "__address__",
                    },
                    {
                        "action": "labelmap",
                        "regex": "__meta_kubernetes_pod_label_(.+)",
                    },
                    {
                        "source_labels": ["__meta_kubernetes_namespace"],
                        "action": "replace",
                        "target_label": "kubernetes_namespace",
                    },
                    {
                        "source_labels": ["__meta_kubernetes_pod_name"],
                        "action": "replace",
                        "target_label": "kubernetes_pod_name",
                    },
                ],
            },
            {
                "job_name": "kube-state-metrics",
                "static_configs": [
                    {"targets": [f"kube-state-metrics.{self.namespace}.svc.cluster.local:8080"]}
                ],
            },
            {
                "job_name": "kubernetes-cadvisor",
                "scheme": "https",
                "tls_config": {"ca_file": "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"},
                "bearer_token_file": "/var/run/secrets/kubernetes.io/serviceaccount/token",
                "kubernetes_sd_configs": [{"role": "node"}],
                "relabel_configs": [
                    {"action": "labelmap", "regex": "__meta_kubernetes_node_label_(.+)"},
                    {"target_label": "__address__", "replacement": "kubernetes.default.svc:443"},
                    {
                        "source_labels": ["__meta_kubernetes_node_name"],
                        "regex": "(.+)",
                        "target_label": "__metrics_path__",
                        "replacement": "/api/v1/nodes/${1}/proxy/metrics/cadvisor",
                    },
                ],
            },
            {
                "job_name": "kubernetes-service-endpoints",
                "kubernetes_sd_configs": [{"role": "endpoints"}],
                "relabel_configs": [
                    {
                        "source_labels": [
                            "__meta_kubernetes_service_annotation_prometheus_io_scrape"
                        ],
                        "action": "keep",
                        "regex": "true",
                    },
                    {
                        "source_labels": [
                            "__meta_kubernetes_service_annotation_prometheus_io_scheme"
                        ],
                        "action": "replace",
                        "target_label": "__scheme__",
                        "regex": "(https?)",
                    },
                    {
                        "source_labels": [
                            "__meta_kubernetes_service_annotation_prometheus_io_path"
                        ],
                        "action": "replace",
                        "target_label": "__metrics_path__",
                        "regex": "(.+)",
                    },
                    {
                        "source_labels": [
                            "__address__",
                            "__meta_kubernetes_service_annotation_prometheus_io_port",
                        ],
                        "action": "replace",
                        "target_label": "__address__",
                        "regex": "([^:]+)(?::\d+)?;(\d+)",  # noqa: W605
                        "replacement": "$1:$2",
                    },
                    {"action": "labelmap", "regex": "__meta_kubernetes_service_label_(.+)"},
                    {
                        "source_labels": ["__meta_kubernetes_namespace"],
                        "action": "replace",
                        "target_label": "kubernetes_namespace",
                    },
                    {
                        "source_labels": ["__meta_kubernetes_service_name"],
                        "action": "replace",
                        "target_label": "kubernetes_name",
                    },
                ],
            },
        ]
