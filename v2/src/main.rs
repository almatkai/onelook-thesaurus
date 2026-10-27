#[tokio::main(worker_threads = 2)]
async fn main() {
    let result = match tezbar_onelook_thesaurus::Port::production() {
        Ok(port) => tezbar_extension_sdk::serve(port).await,
        Err(error) => Err(error),
    };
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
