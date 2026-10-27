//! Execute actual pinned pure host producer/annotator with minimal owned data.
use serde_json::{json, Value};
use std::sync::Arc;
use tezbar_extension_sdk::CoreResult;
struct Process {
    generation: String,
}
struct Entry {
    canonical: String,
    command: String,
    process: Arc<Process>,
    policy: Value,
}
include!("../fixtures/derived/host-annotate.rs");
#[test]
fn actual_host_annotates_current_identity_and_preserves_inert_modes() {
    let e = Entry {
        canonical: "com.tezbar.native.onelook-thesaurus".into(),
        command: "search".into(),
        process: Arc::new(Process {
            generation: "owned-generation".into(),
        }),
        policy: json!({"refreshMs":null}),
    };
    let view = annotate(
        &e,
        "owned-session",
        json!({"ok":true,"mode":"view","sessionId":"forged","root":{"type":"List"}}),
    )
    .unwrap();
    assert_eq!(view["sessionId"], "owned-session");
    assert_eq!(view["extensionId"], e.canonical);
    assert_eq!(view["generation"], "owned-generation");
    assert!(view["refreshMs"].is_null());
    for mode in ["unchanged", "no-view"] {
        let v = json!({"ok":true,"mode":mode});
        assert_eq!(annotate(&e, "owned-session", v.clone()).unwrap(), v);
    }
    assert!(annotate(&e, "s", json!({"mode":"view"})).is_err());
    assert!(annotate(&e, "s", json!({"ok":true,"mode":"other"})).is_err());
}
#[test]
fn actual_host_launch_payload_produces_null_optional_search_text() {
    let id = "owned-session";
    let command = "search";
    let preferences = json!({});
    let body = json!({"argumentValues":{}});
    let payload = include!("../fixtures/derived/host-open-payload.rs");
    assert!(payload["searchText"].is_null());
    assert!(payload["launchContext"].is_null());
    assert_eq!(payload["argumentValues"], json!({}));
    assert_eq!(payload["sessionId"], id);
}
