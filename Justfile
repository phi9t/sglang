# Justfile for SGLang local workflows

# Run the containerized GPT-OSS-120B GSM8k validation benchmark
# using docker compose and local GPUs. This wraps
# scripts/run_container_gptoss_gsm8k_benchmark.sh.

validate-gptoss-gsm8k:
	@scripts/run_container_gptoss_gsm8k_benchmark.sh

