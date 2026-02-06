use std::time::Duration;

use tonic::{transport::Channel, Request};
use tracing::debug;

#[allow(clippy::all)]
pub mod proto {
    #![allow(clippy::all, unused_qualifications)]
    tonic::include_proto!("sglang.grpc.execution");
}

#[derive(Clone)]
pub struct FerricExecutionWorkerClient {
    client: proto::sglang_execution_worker_client::SglangExecutionWorkerClient<Channel>,
}

impl FerricExecutionWorkerClient {
    pub async fn connect(endpoint: &str) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        debug!("Connecting to Ferric execution worker at {}", endpoint);

        let http_endpoint = if let Some(addr) = endpoint.strip_prefix("grpc://") {
            format!("http://{}", addr)
        } else {
            endpoint.to_string()
        };

        let channel = Channel::from_shared(http_endpoint)?
            .http2_keep_alive_interval(Duration::from_secs(30))
            .keep_alive_timeout(Duration::from_secs(10))
            .keep_alive_while_idle(true)
            .tcp_keepalive(Some(Duration::from_secs(60)))
            .tcp_nodelay(true)
            .http2_adaptive_window(true)
            .initial_stream_window_size(Some(16 * 1024 * 1024))
            .initial_connection_window_size(Some(32 * 1024 * 1024))
            .connect()
            .await?;

        Ok(Self {
            client: proto::sglang_execution_worker_client::SglangExecutionWorkerClient::new(
                channel,
            ),
        })
    }

    pub async fn health_check(
        &self,
    ) -> Result<proto::HealthCheckResponse, Box<dyn std::error::Error + Send + Sync>> {
        let mut client = self.client.clone();
        let response = client
            .health_check(Request::new(proto::HealthCheckRequest {}))
            .await?;
        Ok(response.into_inner())
    }

    pub async fn execute_prefill(
        &self,
        req: proto::ExecuteBatchRequest,
    ) -> Result<proto::ExecuteBatchResponse, Box<dyn std::error::Error + Send + Sync>> {
        let mut client = self.client.clone();
        let response = client.execute_prefill(Request::new(req)).await?;
        Ok(response.into_inner())
    }

    pub async fn execute_decode(
        &self,
        req: proto::ExecuteBatchRequest,
    ) -> Result<proto::ExecuteBatchResponse, Box<dyn std::error::Error + Send + Sync>> {
        let mut client = self.client.clone();
        let response = client.execute_decode(Request::new(req)).await?;
        Ok(response.into_inner())
    }

    pub async fn cancel(
        &self,
        request_id: String,
    ) -> Result<proto::CancelResponse, Box<dyn std::error::Error + Send + Sync>> {
        let mut client = self.client.clone();
        let response = client
            .cancel(Request::new(proto::CancelRequest { request_id }))
            .await?;
        Ok(response.into_inner())
    }

    pub async fn get_worker_info(
        &self,
    ) -> Result<proto::GetWorkerInfoResponse, Box<dyn std::error::Error + Send + Sync>> {
        let mut client = self.client.clone();
        let response = client
            .get_worker_info(Request::new(proto::GetWorkerInfoRequest {}))
            .await?;
        Ok(response.into_inner())
    }
}
