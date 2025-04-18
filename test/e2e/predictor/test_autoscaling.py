# Copyright 2022 The KServe Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import uuid

import pytest
from kubernetes import client
from kubernetes.client import V1ResourceRequirements

from kserve import (
    constants,
    KServeClient,
    V1beta1InferenceService,
    V1beta1InferenceServiceSpec,
    V1beta1PredictorSpec,
    V1beta1SKLearnSpec,
    V1beta1AutoScalingSpec,
    V1beta1ResourceMetricSource,
    V1beta1MetricTarget,
    V1beta1ExternalMetricSource,
    V1beta1MetricIdentifier,
    V1beta1MetricsSpec,
)
from ..common.utils import KSERVE_TEST_NAMESPACE
from ..common.utils import predict_isvc

TARGET = "autoscaling.knative.dev/target"
METRIC = "autoscaling.knative.dev/metric"
MODEL = "gs://kfserving-examples/models/sklearn/1.0/model"
INPUT = "./data/iris_input.json"


@pytest.mark.predictor
@pytest.mark.asyncio(scope="session")
async def test_sklearn_kserve_concurrency(rest_v1_client):
    service_name = "isvc-sklearn-scale-concurrency"
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        scale_metric="concurrency",
        scale_target=2,
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )
    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    pods = kserve_client.core_api.list_namespaced_pod(
        KSERVE_TEST_NAMESPACE,
        label_selector="serving.kserve.io/inferenceservice={}".format(service_name),
    )

    isvc_annotations = pods.items[0].metadata.annotations

    res = await predict_isvc(rest_v1_client, service_name, INPUT)
    assert res["predictions"] == [1, 1]
    assert isvc_annotations[METRIC] == "concurrency"
    assert isvc_annotations[TARGET] == "2"
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.predictor
@pytest.mark.asyncio(scope="session")
async def test_sklearn_kserve_rps(rest_v1_client):
    service_name = "isvc-sklearn-scale-rps"
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        scale_metric="rps",
        scale_target=5,
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    pods = kserve_client.core_api.list_namespaced_pod(
        KSERVE_TEST_NAMESPACE,
        label_selector="serving.kserve.io/inferenceservice={}".format(service_name),
    )

    annotations = pods.items[0].metadata.annotations

    assert annotations[METRIC] == "rps"
    assert annotations[TARGET] == "5"
    res = await predict_isvc(rest_v1_client, service_name, INPUT)
    assert res["predictions"] == [1, 1]
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.skip()
@pytest.mark.asyncio(scope="session")
async def test_sklearn_kserve_cpu(rest_v1_client):
    service_name = "isvc-sklearn-scale-cpu"
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        scale_metric="cpu",
        scale_target=50,
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    annotations = {}
    annotations["autoscaling.knative.dev/class"] = "hpa.autoscaling.knative.dev"

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE, annotations=annotations
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    pods = kserve_client.core_api.list_namespaced_pod(
        KSERVE_TEST_NAMESPACE,
        label_selector="serving.kserve.io/inferenceservice={}".format(service_name),
    )

    isvc_annotations = pods.items[0].metadata.annotations

    assert isvc_annotations[METRIC] == "cpu"
    assert isvc_annotations[TARGET] == "50"
    res = await predict_isvc(rest_v1_client, service_name, INPUT)
    assert res["predictions"] == [1, 1]
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.raw
@pytest.mark.asyncio(scope="session")
async def test_sklearn_scale_raw(rest_v1_client, network_layer):
    suffix = str(uuid.uuid4())[1:6]
    service_name = "isvc-sklearn-scale-raw-" + suffix
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        scale_metric="cpu",
        scale_target=50,
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    annotations = {}
    annotations["serving.kserve.io/deploymentMode"] = "RawDeployment"

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE, annotations=annotations
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    api_instance = kserve_client.api_instance
    hpa_resp = api_instance.list_namespaced_custom_object(
        group="autoscaling",
        version="v1",
        namespace=KSERVE_TEST_NAMESPACE,
        label_selector=f"serving.kserve.io/inferenceservice=" f"{service_name}",
        plural="horizontalpodautoscalers",
    )

    assert hpa_resp["items"][0]["spec"]["targetCPUUtilizationPercentage"] == 50
    res = await predict_isvc(
        rest_v1_client, service_name, INPUT, network_layer=network_layer
    )
    assert res["predictions"] == [1, 1]
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.raw
@pytest.mark.asyncio(scope="session")
async def test_sklearn_rolling_update():
    suffix = str(uuid.uuid4())[1:6]
    service_name = "isvc-sklearn-rolling-update-" + suffix
    min_replicas = 4
    predictor = V1beta1PredictorSpec(
        min_replicas=min_replicas,
        scale_metric="cpu",
        scale_target=50,
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    annotations = {}
    annotations["serving.kserve.io/deploymentMode"] = "RawDeployment"

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name,
            namespace=KSERVE_TEST_NAMESPACE,
            annotations=annotations,
            labels={"serving.kserve.io/test": "rolling-update"},
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    updated_annotations = {}
    updated_annotations["serving.kserve.io/deploymentMode"] = "RawDeployment"
    updated_annotations["serving.kserve.io/customAnnotation"] = "TestAnnotation"

    updated_isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name,
            namespace=KSERVE_TEST_NAMESPACE,
            annotations=updated_annotations,
            labels={"serving.kserve.io/test": "rolling-update"},
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)

    kserve_client.patch(service_name, updated_isvc)
    deployment = kserve_client.app_api.list_namespaced_deployment(
        namespace=KSERVE_TEST_NAMESPACE,
        label_selector="serving.kserve.io/test=rolling-update",
    )
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)

    # Check if the deployment replicas still remain the same as min_replicas
    assert deployment.items[0].spec.replicas == min_replicas
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.raw
@pytest.mark.asyncio(scope="session")
async def test_sklearn_keda_scale_existing_spec(rest_v1_client, network_layer):
    """
    Test KEDA autoscaling with existing InferenceService spec
    """
    service_name = "isvc-sklearn-keda-scale"
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        max_replicas=5,
        scale_metric="memory",
        scale_metric_type="Utilization",
        scale_target=50,
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    annotations = {}
    annotations["serving.kserve.io/deploymentMode"] = "RawDeployment"
    annotations["serving.kserve.io/autoscalerClass"] = "keda"

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE, annotations=annotations
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    api_instance = kserve_client.api_instance

    scaledobject_resp = api_instance.list_namespaced_custom_object(
        group="keda.sh",
        version="v1alpha1",
        namespace=KSERVE_TEST_NAMESPACE,
        label_selector=f"serving.kserve.io/inferenceservice={service_name}",
        plural="scaledobjects",
    )

    assert (
        scaledobject_resp["items"][0]["spec"]["triggers"][0]["metricType"]
        == "Utilization"
    )
    assert scaledobject_resp["items"][0]["spec"]["triggers"][0]["type"] == "memory"
    res = await predict_isvc(
        rest_v1_client, service_name, INPUT, network_layer=network_layer
    )
    assert res["predictions"] == [1, 1]
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.raw
@pytest.mark.asyncio(scope="session")
async def test_sklearn_keda_scale_new_spec_resource(rest_v1_client, network_layer):
    """
    Test KEDA autoscaling with new InferenceService (auto_scaling) spec
    """
    service_name = "isvc-sklearn-keda-scale-new-spec"
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        max_replicas=5,
        auto_scaling=V1beta1AutoScalingSpec(
            metrics=[
                V1beta1MetricsSpec(
                    type="Resource",
                    resource=V1beta1ResourceMetricSource(
                        name="memory",
                        target=V1beta1MetricTarget(
                            type="Utilization", average_utilization=50
                        ),
                    ),
                )
            ]
        ),
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    annotations = {}
    annotations["serving.kserve.io/deploymentMode"] = "RawDeployment"
    annotations["serving.kserve.io/autoscalerClass"] = "keda"

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE, annotations=annotations
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    api_instance = kserve_client.api_instance

    scaledobject_resp = api_instance.list_namespaced_custom_object(
        group="keda.sh",
        version="v1alpha1",
        namespace=KSERVE_TEST_NAMESPACE,
        label_selector=f"serving.kserve.io/inferenceservice={service_name}",
        plural="scaledobjects",
    )

    assert (
        scaledobject_resp["items"][0]["spec"]["triggers"][0]["metricType"]
        == "Utilization"
    )
    assert scaledobject_resp["items"][0]["spec"]["triggers"][0]["type"] == "memory"
    res = await predict_isvc(
        rest_v1_client, service_name, INPUT, network_layer=network_layer
    )
    assert res["predictions"] == [1, 1]
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)


@pytest.mark.raw
@pytest.mark.asyncio(scope="session")
async def test_sklearn_keda_scale_new_spec_external(rest_v1_client, network_layer):
    """
    Test KEDA autoscaling with new InferenceService (auto_scaling) spec
    """
    service_name = "isvc-sklearn-keda-scale-new-spec-2"
    predictor = V1beta1PredictorSpec(
        min_replicas=1,
        max_replicas=5,
        auto_scaling=V1beta1AutoScalingSpec(
            metrics=[
                V1beta1MetricsSpec(
                    type="External",
                    external=V1beta1ExternalMetricSource(
                        metric=V1beta1MetricIdentifier(
                            backend="prometheus",
                            server_address="http://prometheus:9090",
                            query="http_requests_per_second",
                        ),
                        target=V1beta1MetricTarget(type="Value", value=50),
                    ),
                )
            ]
        ),
        sklearn=V1beta1SKLearnSpec(
            storage_uri=MODEL,
            resources=V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "128Mi"},
                limits={"cpu": "100m", "memory": "256Mi"},
            ),
        ),
    )

    annotations = {}
    annotations["serving.kserve.io/deploymentMode"] = "RawDeployment"
    annotations["serving.kserve.io/autoscalerClass"] = "keda"

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND_INFERENCESERVICE,
        metadata=client.V1ObjectMeta(
            name=service_name, namespace=KSERVE_TEST_NAMESPACE, annotations=annotations
        ),
        spec=V1beta1InferenceServiceSpec(predictor=predictor),
    )

    kserve_client = KServeClient(
        config_file=os.environ.get("KUBECONFIG", "~/.kube/config")
    )
    kserve_client.create(isvc)
    kserve_client.wait_isvc_ready(service_name, namespace=KSERVE_TEST_NAMESPACE)
    api_instance = kserve_client.api_instance

    scaledobject_resp = api_instance.list_namespaced_custom_object(
        group="keda.sh",
        version="v1alpha1",
        namespace=KSERVE_TEST_NAMESPACE,
        label_selector=f"serving.kserve.io/inferenceservice={service_name}",
        plural="scaledobjects",
    )

    trigger_metadata = scaledobject_resp["items"][0]["spec"]["triggers"][0]["metadata"]
    trigger_type = scaledobject_resp["items"][0]["spec"]["triggers"][0]["type"]
    assert trigger_type == "prometheus"
    assert trigger_metadata["query"] == "http_requests_per_second"
    assert trigger_metadata["serverAddress"] == "http://prometheus:9090"
    assert trigger_metadata["threshold"] == "50"
    res = await predict_isvc(
        rest_v1_client, service_name, INPUT, network_layer=network_layer
    )
    assert res["predictions"] == [1, 1]
    kserve_client.delete(service_name, KSERVE_TEST_NAMESPACE)
