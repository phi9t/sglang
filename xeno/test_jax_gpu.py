#!/usr/bin/env python3
import sys


def main() -> int:
    try:
        import jax
        import jaxlib
        from jax import numpy as jnp
    except Exception as exc:  # pragma: no cover - simple smoke script
        print(f"[JAX] Import failed: {exc}", file=sys.stderr)
        return 1

    print(f"[JAX] jax={jax.__version__} jaxlib={jaxlib.__version__}")

    devs = jax.devices()
    print(f"[JAX] devices={devs}")
    if not devs:
        print("[JAX] No devices detected", file=sys.stderr)
        return 1

    # Prefer GPU if available
    gpu_devs = [d for d in devs if d.platform == "gpu" or d.platform == "cuda"]
    if gpu_devs:
        dev = gpu_devs[0]
        print(f"[JAX] Using GPU device: {dev}")
    else:
        dev = devs[0]
        print(f"[JAX] Using non-GPU device: {dev}")

    x = jnp.ones((512, 512), dtype=jnp.float32)
    x = jax.device_put(x, dev)
    y = jnp.dot(x, x)
    val = float(y[0, 0])
    print(f"[JAX] dot(ones, ones)[0,0] = {val}")

    if abs(val - 512.0) > 1e-3:
        print("[JAX] Unexpected result value", file=sys.stderr)
        return 1

    print("[JAX] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry
    raise SystemExit(main())

