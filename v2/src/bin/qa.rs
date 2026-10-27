//! QA-only executable: explicit owned TLS endpoint, never shipped in the ZIP.
#[tokio::main(worker_threads = 2)]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        3,
        "QA executable requires owned TLS URL and PEM path"
    );
    let cert = std::fs::read(&args[2]).expect("owned certificate");
    let http =
        tezbar_onelook_thesaurus::http::Http::owned_tls(args[1].parse().expect("owned URL"), &cert)
            .expect("owned TLS");
    tezbar_extension_sdk::serve(tezbar_onelook_thesaurus::Port::with_http(http))
        .await
        .expect("QA protocol");
}
