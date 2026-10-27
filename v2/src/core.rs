//! Source-derived domain rules. No host, JavaScript, or fixture dependency.
use serde::{Deserialize, Serialize};

pub const SERVICE: &str = "https://api.datamuse.com/words?qe=ml&md=d&ml=";
pub const MAX_QUERY: usize = 4096;
pub const MAX_BODY: usize = 512 * 1024;
pub const MAX_ROWS: usize = 1000;
pub const MAX_VIEW: usize = 4 * 1024 * 1024;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Word {
    pub word: String,
    #[serde(default)]
    pub defs: Option<Vec<String>>,
}

/// Deliberately the source's replaceAll(" ", "+"), not encodeURIComponent.
/// &, +, #, %, tabs and Unicode retain the original WHATWG URL interpretation.
pub fn raw_url(query: &str) -> Result<String, String> {
    if query.len() > MAX_QUERY {
        return Err("Query exceeds 4096 UTF-8 bytes. Shorten it and try again.".into());
    }
    Ok(format!("{SERVICE}{}", query.replace(' ', "+")))
}

pub fn format_pos(text: &str) -> String {
    // JS /\w/ without u/i is ASCII [A-Za-z0-9_]. Replace only the first match.
    let bytes = text.as_bytes();
    for tab in 1..bytes.len() {
        if bytes[tab] != b'\t'
            || !(bytes[tab - 1].is_ascii_alphanumeric() || bytes[tab - 1] == b'_')
        {
            continue;
        }
        let mut start = tab - 1;
        while start > 0 && (bytes[start - 1].is_ascii_alphanumeric() || bytes[start - 1] == b'_') {
            start -= 1;
        }
        return format!(
            "{}`{}` {}",
            &text[..start],
            &text[start..tab],
            &text[tab + 1..]
        );
    }
    text.into()
}

impl Word {
    pub fn subtitle(&self) -> Option<&str> {
        self.defs
            .as_ref()?
            .first()
            .map(String::as_str)
            .filter(|s| !s.is_empty())
    }
    pub fn markdown(&self) -> String {
        format!(
            "# {}\n---\n{}",
            self.word,
            self.defs
                .as_ref()
                .map(|defs| defs
                    .iter()
                    .map(|s| format_pos(s))
                    .collect::<Vec<_>>()
                    .join("\n\n"))
                .unwrap_or_default()
        )
    }
}

pub fn validate_words(words: &[Word]) -> Result<(), String> {
    if words.len() > MAX_ROWS {
        return Err(
            "Response exceeds 1000 rows; no results were truncated. Refine the query.".into(),
        );
    }
    for word in words {
        if word.word.len() > 4096
            || word
                .defs
                .as_ref()
                .is_some_and(|d| d.len() > 64 || d.iter().any(|s| s.len() > 8192))
        {
            return Err(
                "Response word/definition limit exceeded; no results were truncated.".into(),
            );
        }
    }
    Ok(())
}
pub fn parse_words(body: &[u8]) -> Result<Vec<Word>, String> {
    if body.len() > MAX_BODY {
        return Err(
            "Response exceeds 512 KiB; no results were truncated. Refine the query.".into(),
        );
    }
    let words: Vec<Word> = serde_json::from_slice(body).map_err(|_| {
        "Datamuse returned an invalid word/definition response. Retry manually.".to_string()
    })?;
    validate_words(&words)?;
    Ok(words)
}

/// Actual locked utils fetch-utils.ts MIME recognition, including text/json
/// and word-boundary JSON suffixes. Non-JSON text cannot satisfy Word[].
pub fn is_json(content_type: &str) -> bool {
    let mime = content_type
        .split(';')
        .next()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();
    let Some((kind, subtype)) = mime.split_once('/') else {
        return false;
    };
    let valid = |s: &str, extra: &[u8]| {
        !s.is_empty()
            && s.len() <= 127
            && s.as_bytes()[0].is_ascii_alphanumeric()
            && s.bytes()
                .all(|b| b.is_ascii_alphanumeric() || extra.contains(&b))
    };
    if !valid(kind, b"!#$&^_-") || !valid(subtype, b"!#$&^_.+-") {
        return false;
    }
    // JS \b uses ASCII word characters, so underscore does not delimit JSON.
    subtype
        .split(|c: char| !c.is_ascii_alphanumeric() && c != '_')
        .any(|part| part == "json")
}
