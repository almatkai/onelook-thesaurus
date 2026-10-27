use crate::{
    core::{raw_url, validate_words, Word, MAX_BODY, MAX_VIEW},
    http::Http,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{HashMap, VecDeque},
    io::{Read, Write},
    path::PathBuf,
    sync::{Arc, Mutex},
};
use tezbar_extension_sdk::{unchanged, view, BoxFuture, CoreResult, Extension, ExtensionContext};

const CACHE_BYTES: usize = 2 * 1024 * 1024;
const CACHE_ENTRIES: usize = 8;
type Sessions = Mutex<HashMap<String, Arc<Mutex<State>>>>;
#[derive(Clone, Copy)]
enum Action {
    Toggle,
    Retry,
}
#[derive(Default)]
struct State {
    owner: Option<ExtensionContext>,
    query: String,
    invalid_draft: bool,
    request: u64,
    words: Arc<Vec<Word>>,
    show_details: bool,
    error: Option<String>,
    warning: Option<String>,
    actions: HashMap<String, Action>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Entry {
    key: String,
    words: Vec<Word>,
}
#[derive(Default)]
struct Cache {
    entries: VecDeque<Entry>,
    file: Option<PathBuf>,
    warning: Option<String>,
}
impl Cache {
    fn get(&self, query: &str) -> Arc<Vec<Word>> {
        let key = raw_url(query).ok();
        Arc::new(
            self.entries
                .iter()
                .find(|e| Some(&e.key) == key.as_ref())
                .map(|e| e.words.clone())
                .unwrap_or_default(),
        )
    }
    fn load(&mut self, ctx: &ExtensionContext) {
        let path = ctx.paths.data_dir.join("datamuse-cache-v1.json");
        self.file = Some(path.clone());
        let loaded = (|| -> Result<VecDeque<Entry>, String> {
            let mut file = match std::fs::File::open(&path) {
                Ok(f) => f,
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(VecDeque::new()),
                Err(_) => return Err("Cache could not be read; using memory only.".into()),
            };
            let mut bytes = Vec::new();
            Read::by_ref(&mut file)
                .take((CACHE_BYTES + 1) as u64)
                .read_to_end(&mut bytes)
                .map_err(|_| "Cache could not be read; using memory only.")?;
            if bytes.len() > CACHE_BYTES {
                return Err("Cache exceeds 2 MiB; using memory only.".into());
            }
            let entries: VecDeque<Entry> = serde_json::from_slice(&bytes)
                .map_err(|_| "Cache is invalid; using memory only.")?;
            if entries.len() > CACHE_ENTRIES {
                return Err("Cache exceeds 8 entries; using memory only.".into());
            }
            let mut seen = std::collections::HashSet::new();
            for entry in &entries {
                if !entry.key.starts_with(crate::core::SERVICE)
                    || entry.key.len() > crate::core::SERVICE.len() + crate::core::MAX_QUERY
                    || !seen.insert(&entry.key)
                    || serde_json::to_vec(&entry.words)
                        .map_err(|_| "Invalid cache")?
                        .len()
                        > MAX_BODY
                {
                    return Err("Cache is invalid; using memory only.".into());
                }
                validate_words(&entry.words)?;
            }
            Ok(entries)
        })();
        match loaded {
            Ok(entries) => self.entries = entries,
            Err(error) => {
                self.warning = Some(error);
                self.file = None;
            }
        }
    }
    // Synchronous, bounded final commit: no detached writer may outlive cancellation
    // and replace a newer snapshot. Cache eviction never truncates visible results.
    fn put(&mut self, query: &str, words: &[Word]) -> Result<(), String> {
        let key = raw_url(query)?;
        self.entries.retain(|e| e.key != key);
        self.entries.push_front(Entry {
            key,
            words: words.to_vec(),
        });
        while self.entries.len() > CACHE_ENTRIES
            || serde_json::to_vec(&self.entries)
                .map_err(|_| "Cache encoding failed")?
                .len()
                > CACHE_BYTES
        {
            self.entries.pop_back();
        }
        if let Some(path) = &self.file {
            let bytes = serde_json::to_vec(&self.entries).map_err(|_| "Cache encoding failed")?;
            let result = (|| -> std::io::Result<()> {
                std::fs::create_dir_all(path.parent().expect("cache parent"))?;
                let tmp = path.with_extension(format!("tmp-{}", uuid::Uuid::new_v4()));
                let write = (|| -> std::io::Result<()> {
                    let mut f = std::fs::OpenOptions::new()
                        .write(true)
                        .create_new(true)
                        .open(&tmp)?;
                    f.write_all(&bytes)?;
                    f.sync_all()?;
                    // rename replaces atomically on Unix. On Windows an existing
                    // target can fail; report that and retain its previous bytes.
                    std::fs::rename(&tmp, path)
                })();
                if write.is_err() {
                    let _ = std::fs::remove_file(tmp);
                }
                write
            })();
            result.map_err(|_| {
                "Results loaded, but cache could not be saved. Previous disk cache retained."
                    .to_string()
            })?;
        }
        Ok(())
    }
}

pub struct Port {
    http: Http,
    sessions: Sessions,
    cache: Mutex<Cache>,
}
struct OpenGuard<'a> {
    registry: &'a Sessions,
    id: String,
    state: Arc<Mutex<State>>,
    complete: bool,
}
impl Drop for OpenGuard<'_> {
    fn drop(&mut self) {
        if !self.complete {
            let mut sessions = self.registry.lock().expect("registry mutex");
            if sessions
                .get(&self.id)
                .is_some_and(|s| Arc::ptr_eq(s, &self.state))
            {
                sessions.remove(&self.id);
            }
        }
    }
}
impl Port {
    fn prune_cancelled(&self) {
        // The SDK may cancel an open after our future returned without invoking
        // dispose. Retain its context solely as a cancellation witness. Poll it
        // once, without spawning work, before every registry use/capacity check.
        use std::{
            future::Future,
            task::{Context, Poll, Waker},
        };
        let mut cx = Context::from_waker(Waker::noop());
        self.sessions
            .lock()
            .expect("registry mutex")
            .retain(|_, state| {
                let state = state.lock().expect("state mutex");
                let owner = state.owner.as_ref().expect("registered owner");
                let cancelled = owner.cancelled();
                tokio::pin!(cancelled);
                !matches!(cancelled.as_mut().poll(&mut cx), Poll::Ready(()))
            });
    }
    pub fn production() -> Result<Self, String> {
        Ok(Self::with_http(Http::production()?))
    }
    pub fn with_http(http: Http) -> Self {
        Self {
            http,
            sessions: Mutex::default(),
            cache: Mutex::default(),
        }
    }
    fn render(state: &mut State) -> CoreResult {
        state.actions.clear();
        let toggle = if state.words.is_empty() {
            None
        } else {
            let id = format!("toggle:{}", uuid::Uuid::new_v4());
            state.actions.insert(id.clone(), Action::Toggle);
            Some(id)
        };
        let mut actions = Vec::new();
        if let Some(id) = &toggle {
            actions.push(json!({"id":id,"title":"Toggle Definitions","kind":"action"}));
        }
        if state.error.is_some()
            && !state.invalid_draft
            && !state.query.is_empty()
            && raw_url(&state.query).is_ok()
        {
            let id = format!("retry:{}", uuid::Uuid::new_v4());
            state.actions.insert(id.clone(), Action::Retry);
            actions.push(json!({"id":id,"title":"Retry","kind":"action"}));
        }
        let mut children: Vec<Value> = state.words.iter().enumerate().map(|(index, word)| {
            let mut props = json!({"id":index.to_string(),"title":word.word,"actionIds":actions.iter().map(|a| &a["id"]).collect::<Vec<_>>()});
            if let Some(subtitle) = word.subtitle() { props["subtitle"] = json!(subtitle); }
            if state.show_details { props["detail"] = json!({"type":"List.Item.Detail","props":{"markdown":word.markdown()}}); }
            json!({"type":"List.Item","props":props})
        }).collect();
        children.push(json!({"type":"List.EmptyView","props":{"title":if state.query.is_empty() { "Enter a word, phrase, description, or pattern" } else { "No results" },"description":""}}));
        let mut result = view(
            "OneLook Thesaurus",
            json!({"type":"List","props":{"searchText":state.query,"searchBarPlaceholder":"Enter a word, phrase, description, or pattern","__hasServerSearch":true,"isShowingDetail":state.show_details,"isLoading":false,"throttle":true},"children":children}),
            actions,
        );
        if state.invalid_draft {
            result["root"]["props"]
                .as_object_mut()
                .expect("root props")
                .remove("searchText");
        }
        result["refreshMs"] = Value::Null;
        let messages: Vec<&str> = [state.error.as_deref(), state.warning.as_deref()]
            .into_iter()
            .flatten()
            .collect();
        if !messages.is_empty() {
            result["message"] = json!(messages.join(" "));
        }
        if serde_json::to_vec(&result)
            .map_err(|_| "View encoding failed")?
            .len()
            > MAX_VIEW
        {
            state.actions.clear();
            return Err("View exceeds 4 MiB; no results were truncated. Refine the query.".into());
        }
        Ok(result)
    }
    async fn search(
        &self,
        ctx: &ExtensionContext,
        session: &Arc<Mutex<State>>,
        query: String,
    ) -> CoreResult {
        // Own query and revoke every old action synchronously before FIRST await.
        let request = {
            let mut s = session.lock().expect("state mutex");
            s.request = s
                .request
                .checked_add(1)
                .ok_or("Request revision exhausted")?;
            s.actions.clear();
            s.error = None;
            let cache = self.cache.lock().expect("cache mutex");
            s.words = cache.get(&query);
            s.warning = cache.warning.clone();
            if let Err(error) = raw_url(&query) {
                s.invalid_draft = true;
                s.query.clear();
                s.error = Some(error);
                s.words = Arc::default();
                return Self::render(&mut s);
            }
            s.invalid_draft = false;
            s.query = query.clone();
            s.request
        };
        if query.is_empty() {
            return Self::render(&mut session.lock().expect("state mutex"));
        }
        let fetched = tokio::select! { biased; _ = ctx.cancelled() => return Err("Operation cancelled".into()), result = self.http.search(&query) => result };
        // No await between ownership validation and final state/cache commit.
        let mut s = session.lock().expect("state mutex");
        if s.request != request || s.query != query {
            return Ok(unchanged());
        }
        match fetched {
            Ok(words) => {
                s.warning = self
                    .cache
                    .lock()
                    .expect("cache mutex")
                    .put(&query, &words)
                    .err()
                    .or(s.warning.take());
                s.words = Arc::new(words);
            }
            Err(error) => s.error = Some(error),
        }
        Self::render(&mut s)
    }
}
impl Extension for Port {
    fn id(&self) -> &'static str {
        "com.tezbar.native.onelook-thesaurus"
    }
    fn version(&self) -> &'static str {
        env!("CARGO_PKG_VERSION")
    }
    fn commands(&self) -> &'static [&'static str] {
        &["search"]
    }
    fn initialize<'a>(&'a self, ctx: &'a ExtensionContext) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            self.cache.lock().expect("cache mutex").load(ctx);
            Ok(json!({"ready":true}))
        })
    }
    fn handle<'a>(
        &'a self,
        ctx: &'a ExtensionContext,
        command: &'a str,
        operation: &'a str,
        payload: &'a Value,
        _staged: &'a mut Value,
    ) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            if command != "search" {
                return Err("Unknown command".into());
            }
            let id = payload["sessionId"]
                .as_str()
                .filter(|s| !s.is_empty() && s.len() <= 256)
                .ok_or("Invalid session identity")?;
            self.prune_cancelled();
            if operation == "extension:dispose-session" {
                self.sessions.lock().expect("registry mutex").remove(id);
                return Ok(json!({}));
            }
            if operation == "extension:run-command" {
                let state = Arc::new(Mutex::new(State {
                    owner: Some(ctx.clone()),
                    ..State::default()
                }));
                {
                    let mut sessions = self.sessions.lock().expect("registry mutex");
                    if sessions.len() >= 128 || sessions.contains_key(id) {
                        return Err("Session capacity reached/duplicate session".into());
                    }
                    sessions.insert(id.into(), state.clone());
                }
                let mut guard = OpenGuard {
                    registry: &self.sessions,
                    id: id.into(),
                    state: state.clone(),
                    complete: false,
                };
                // The pinned host producer sends JSON null when no launch
                // search text exists. SDK docs describe this field as optional.
                let query = match payload.get("searchText") {
                    None | Some(Value::Null) => String::new(),
                    Some(Value::String(query)) => query.clone(),
                    _ => return Err("Search text must be a string".into()),
                };
                let result = self.search(ctx, &state, query).await;
                guard.complete = result.is_ok();
                return result;
            }
            let state = self
                .sessions
                .lock()
                .expect("registry mutex")
                .get(id)
                .cloned()
                .ok_or("Unknown session")?;
            match operation {
                "extension:search-text-changed" => {
                    // Invalid intermediate input must revoke old actions/data too.
                    let query = match payload["searchText"].as_str() {
                        Some(q) => q.to_owned(),
                        None => {
                            let mut s = state.lock().expect("state mutex");
                            s.actions.clear();
                            s.invalid_draft = true;
                            s.request = s
                                .request
                                .checked_add(1)
                                .ok_or("Request revision exhausted")?;
                            s.words = Arc::default();
                            s.error = Some("Search text must be a string".into());
                            return Self::render(&mut s);
                        }
                    };
                    self.search(ctx, &state, query).await
                }
                "extension:invoke-action" => {
                    let action = {
                        let mut s = state.lock().expect("state mutex");
                        // Consume OUTSIDE SDK's staged Value, before any await.
                        let Some(action) = payload["actionId"]
                            .as_str()
                            .and_then(|id| s.actions.remove(id))
                        else {
                            return Ok(unchanged());
                        };
                        s.actions.clear();
                        action
                    };
                    match action {
                        Action::Toggle => {
                            let mut s = state.lock().expect("state mutex");
                            s.show_details = !s.show_details;
                            Self::render(&mut s)
                        }
                        Action::Retry => {
                            let query = state.lock().expect("state mutex").query.clone();
                            self.search(ctx, &state, query).await
                        }
                    }
                }
                "extension:refresh-session" | "extension:load-more" => Ok(unchanged()),
                _ => Err("Unsupported operation".into()),
            }
        })
    }
    fn shutdown<'a>(&'a self, _ctx: &'a ExtensionContext) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            self.sessions.lock().expect("registry mutex").clear();
            Ok(json!({}))
        })
    }
}
