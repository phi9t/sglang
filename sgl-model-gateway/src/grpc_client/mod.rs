pub mod ferric_execution_worker;
pub mod sglang_scheduler;
pub mod vllm_engine;

// Export both clients
// Re-export proto modules with explicit names
pub use ferric_execution_worker::{proto as ferric_execution_proto, FerricExecutionWorkerClient};
pub use sglang_scheduler::{proto as sglang_proto, SglangSchedulerClient};
pub use vllm_engine::{proto as vllm_proto, VllmEngineClient};
