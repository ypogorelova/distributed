from __future__ import annotations

import pathlib

import pytest
from tornado.httpclient import AsyncHTTPClient

from distributed import Semaphore
from distributed.utils_test import fetch_metrics_sample_names, gen_cluster, inc


@gen_cluster(client=True)
async def test_scheduler(c, s, a, b):
    client = AsyncHTTPClient()
    response = await client.fetch(f"http://localhost:{s.http_server.port}/health")
    assert response.code == 200


@gen_cluster(client=True, nthreads=[("", 1)])
async def test_prometheus_api_doc(c, s, a):
    """Test that the Sphinx documentation of Prometheus endpoints matches the
    implementation.
    """
    pytest.importorskip("prometheus_client")

    # Some metrics only appear if there are tasks on the cluster
    fut = c.submit(inc, 1)
    await fut
    # Semaphore metrics only appear after semaphores are used
    sem = await Semaphore()
    await sem.acquire()
    await sem.release()

    # Note: built-in Prometheus metrics are undocumented
    scheduler_metrics = await fetch_metrics_sample_names(
        s.http_server.port, prefix="dask_"
    )
    worker_metrics = await fetch_metrics_sample_names(
        a.http_server.port, prefix="dask_"
    )

    try:
        import crick  # noqa: F401

        crick_metrics = set()  # Already in worker_metrics
    except ImportError:
        crick_metrics = {
            "dask_worker_tick_duration_median_seconds",
            "dask_worker_task_duration_median_seconds",
            "dask_worker_transfer_bandwidth_median_bytes",
        }

    implemented = scheduler_metrics | worker_metrics | crick_metrics

    documented = set()
    root_dir = pathlib.Path(__file__).parent.parent.parent.parent
    with open(root_dir / "docs" / "source" / "prometheus.rst") as fh:
        for row in fh:
            row = row.strip()
            if row.startswith("dask_"):
                documented.add(row)

    assert documented == implemented
