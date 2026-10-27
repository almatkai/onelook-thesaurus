fn annotate(e: &Entry, id: &str, mut value: Value) -> CoreResult {
    if !value["ok"].is_boolean() {
        return Err("Invalid extension result".into());
    }
    if value["ok"] == false {
        return Ok(value);
    }
    match value["mode"].as_str() {
        Some("view") => {
            value["sessionId"] = json!(id);
            value["extensionId"] = json!(e.canonical);
            value["commandName"] = json!(e.command);
            value["generation"] = json!(e.process.generation);
            value["refreshMs"] = e.policy.get("refreshMs").cloned().unwrap_or(Value::Null);
        }
        Some("no-view" | "unchanged") => {}
        _ => return Err("Invalid extension view mode".into()),
    }
    Ok(value)
}
