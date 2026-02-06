"""
Standalone Ferric execution-worker gRPC stub server.

This server is intentionally minimal and is used to validate the Rust<->Python
execution-worker boundary contract before wiring real model execution.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

logger = logging.getLogger(__name__)


def _load_proto_modules():
    try:
        from sglang.srt.grpc import (
            sglang_execution_worker_pb2,
            sglang_execution_worker_pb2_grpc,
        )
    except ImportError as e:
        raise RuntimeError(
            "Failed to import generated execution-worker protobuf modules. "
            "Run: python python/sglang/srt/grpc/compile_proto.py"
        ) from e

    return sglang_execution_worker_pb2, sglang_execution_worker_pb2_grpc


class FerricExecutionWorkerServicer:
    """Minimal placeholder implementation of execution-worker service."""

    def __init__(self, pb2):
        self.pb2 = pb2

    async def ExecutePrefill(self, request, context):  # noqa: N802
        return self.pb2.ExecuteBatchResponse(
            batch_id=request.batch_id,
            status=self.pb2.BATCH_STATUS_RETRYABLE_ERROR,
            error_message="Ferric stub: ExecutePrefill not implemented",
        )

    async def ExecuteDecode(self, request, context):  # noqa: N802
        return self.pb2.ExecuteBatchResponse(
            batch_id=request.batch_id,
            status=self.pb2.BATCH_STATUS_RETRYABLE_ERROR,
            error_message="Ferric stub: ExecuteDecode not implemented",
        )

    async def Cancel(self, request, context):  # noqa: N802
        return self.pb2.CancelResponse(
            accepted=False,
            message=f"Ferric stub: cancel not implemented for {request.request_id}",
        )

    async def HealthCheck(self, request, context):  # noqa: N802
        return self.pb2.HealthCheckResponse(
            healthy=True,
            ready=True,
            detail="Ferric execution-worker stub is alive",
        )

    async def GetWorkerInfo(self, request, context):  # noqa: N802
        return self.pb2.GetWorkerInfoResponse(
            worker_id="ferric-stub",
            model_path="",
            model_impl="python_stub",
            device="",
            tp_size=1,
            dp_size=1,
            pp_size=1,
            supports_lora=False,
            supports_hidden_states=False,
            supports_multimodal=False,
        )


async def serve(host: str, port: int):
    try:
        import grpc
    except ImportError as e:
        raise RuntimeError(
            "Failed to import grpc. Install dependency: pip install grpcio"
        ) from e

    pb2, pb2_grpc = _load_proto_modules()

    server = grpc.aio.server()
    pb2_grpc.add_SglangExecutionWorkerServicer_to_server(
        FerricExecutionWorkerServicer(pb2),
        server,
    )
    bind_addr = f"{host}:{port}"
    server.add_insecure_port(bind_addr)

    logger.info("Starting Ferric execution-worker stub on %s", bind_addr)
    await server.start()
    await server.wait_for_termination()


def main():
    parser = argparse.ArgumentParser(
        description="Run Ferric execution-worker gRPC stub server"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=51000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
