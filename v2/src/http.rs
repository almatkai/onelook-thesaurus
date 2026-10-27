use crate::core::{parse_words, raw_url, Word, MAX_BODY};
use reqwest::{redirect::Policy, Client, Url};
use std::time::Duration;

pub struct Http {
    client: Client,
    #[cfg(feature = "qa")]
    endpoint: Option<Url>,
}
impl Http {
    pub fn production() -> Result<Self, String> {
        Self::build(Client::builder())
    }
    fn build(builder: reqwest::ClientBuilder) -> Result<Self, String> {
        Ok(Self {
            client: builder
                .no_proxy()
                .redirect(Policy::none())
                .connect_timeout(Duration::from_secs(5))
                .timeout(Duration::from_secs(15))
                .pool_max_idle_per_host(1)
                .build()
                .map_err(|_| "Could not initialize HTTPS client".to_string())?,
            #[cfg(feature = "qa")]
            endpoint: None,
        })
    }
    #[cfg(feature = "qa")]
    pub fn owned_tls(endpoint: Url, certificate: &[u8]) -> Result<Self, String> {
        if endpoint.scheme() != "https"
            || endpoint.host_str() != Some("127.0.0.1")
            || endpoint.port().is_none()
            || !endpoint.username().is_empty()
            || endpoint.password().is_some()
        {
            return Err("QA endpoint must be an explicitly owned loopback TLS listener".into());
        }
        let cert = reqwest::Certificate::from_pem(certificate)
            .map_err(|_| "Invalid QA certificate".to_string())?;
        let mut http = Self::build(
            Client::builder()
                .tls_built_in_root_certs(false)
                .add_root_certificate(cert),
        )?;
        http.endpoint = Some(endpoint);
        Ok(http)
    }
    pub async fn search(&self, query: &str) -> Result<Vec<Word>, String> {
        let raw = raw_url(query)?;
        let url = Url::parse(&raw)
            .map_err(|_| "The query could not be interpreted as a search URL".to_string())?;
        #[cfg(feature = "qa")]
        let url = if let Some(endpoint) = &self.endpoint {
            let mut owned = endpoint.clone();
            owned.set_path(url.path());
            owned.set_query(url.query());
            owned
        } else {
            url
        };
        let mut response = self
            .client
            .get(url)
            .send()
            .await
            .map_err(|_| "Datamuse request failed or timed out. Retry manually.".to_string())?;
        if !response.status().is_success() {
            return Err(format!(
                "Datamuse returned HTTP {}. Retry manually.",
                response.status().as_u16()
            ));
        }
        let content_type = response
            .headers()
            .get(reqwest::header::CONTENT_TYPE)
            .and_then(|h| h.to_str().ok())
            .unwrap_or("");
        if !crate::core::is_json(content_type) {
            return Err("Datamuse returned a non-JSON response. Retry manually.".into());
        }
        if response
            .content_length()
            .is_some_and(|n| n > MAX_BODY as u64)
        {
            return Err(
                "Response exceeds 512 KiB; no results were truncated. Refine the query.".into(),
            );
        }
        let mut body = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|_| "Datamuse response was interrupted. Retry manually.".to_string())?
        {
            if body.len() + chunk.len() > MAX_BODY {
                return Err(
                    "Response exceeds 512 KiB; no results were truncated. Refine the query.".into(),
                );
            }
            body.extend_from_slice(&chunk);
        }
        parse_words(&body)
    }
}
