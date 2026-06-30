#!/usr/bin/env python3
import os
import sys


def main() -> int:
    try:
        import torch
        import torch.distributed as dist
    except Exception as exc:  # pragma: no cover
        print(f"[TORCH] Import failed: {exc}", file=sys.stderr)
        return 1

    print(f"[TORCH] version={torch.__version__}")

    cuda_ok = torch.cuda.is_available()
    num_dev = torch.cuda.device_count()
    print(f"[TORCH] cuda_available={cuda_ok} num_devices={num_dev}")
    if not cuda_ok or num_dev == 0:
        print("[TORCH] CUDA not available", file=sys.stderr)
        return 1

    x = torch.ones((512, 512), device="cuda", dtype=torch.float32)
    y = x @ x
    val = float(y[0, 0].item())
    print(f"[TORCH] matmul(ones, ones)[0,0] = {val}")
    if abs(val - 512.0) > 1e-3:
        print("[TORCH] Unexpected matmul result", file=sys.stderr)
        return 1

    dist_avail = dist.is_available()
    nccl_avail = dist.is_nccl_available()
    print(f"[TORCH] dist_available={dist_avail} nccl_backend_available={nccl_avail}")
    if not (dist_avail and nccl_avail):
        print("[TORCH] Distributed or NCCL backend not available", file=sys.stderr)
        return 1

    # Note: we do not spawn a multi-process NCCL collective here; that would
    # require a launcher (torchrun / mpirun) and is beyond a quick smoke test.

    print("[TORCH] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

