use serde_json::{json, Value};
use tezbar_onelook_thesaurus::core::*;

#[test]
fn actual_source_url_and_metadata_oracles() {
    let oracle: Value =
        serde_json::from_str(include_str!("../fixtures/source-oracles.json")).unwrap();
    for vector in oracle["vectors"].as_array().unwrap() {
        let raw = raw_url(vector["query"].as_str().unwrap()).unwrap();
        assert_eq!(raw, vector["raw"].as_str().unwrap());
        assert_eq!(
            reqwest::Url::parse(&raw).unwrap().as_str(),
            vector["url"].as_str().unwrap()
        );
    }
    for mime in oracle["mime"].as_array().unwrap() {
        assert_eq!(
            is_json(mime["value"].as_str().unwrap()),
            mime["isJSON"].as_bool().unwrap()
        );
    }
    for row in oracle["words"].as_array().unwrap() {
        let word: Word = serde_json::from_value(row["input"].clone()).unwrap();
        assert_eq!(word.word, row["title"]);
        assert_eq!(
            word.subtitle().map(Value::from).unwrap_or(Value::Null),
            row["subtitle"]
        );
        assert_eq!(word.markdown(), row["markdown"]);
    }
}
#[test]
fn regex_is_js_ascii_and_first_match_only() {
    assert_eq!(format_pos("éadj\tn\tlast"), "é`adj` n\tlast");
    assert_eq!(format_pos("é\t"), "é\t");
    assert_eq!(format_pos("\t1_n\t"), "\t`1_n` ");
}
#[test]
fn data_limits_reject_without_truncation() {
    assert!(raw_url(&"x".repeat(MAX_QUERY)).is_ok());
    assert!(raw_url(&"x".repeat(MAX_QUERY + 1)).is_err());
    assert!(parse_words(&vec![b' '; MAX_BODY + 1]).is_err());
    assert!(validate_words(&vec![
        Word {
            word: "a".into(),
            defs: None
        };
        MAX_ROWS
    ])
    .is_ok());
    assert!(validate_words(&vec![
        Word {
            word: "a".into(),
            defs: None
        };
        MAX_ROWS + 1
    ])
    .is_err());
    for input in [
        json!({}),
        json!([null]),
        json!([{"word":5}]),
        json!([{"word":"x","defs":[null]}]),
        json!([{"word":"x","defs":"bad"}]),
    ] {
        assert!(parse_words(&serde_json::to_vec(&input).unwrap()).is_err());
    }
}
#[test]
fn service_order_and_duplicates_are_not_ranked_or_filtered() {
    let words = parse_words(
        br#"[{"word":"z","score":1},{"word":"a","score":999},{"word":"z","defs":["n\tlast"]}]"#,
    )
    .unwrap();
    assert_eq!(
        words.iter().map(|w| w.word.as_str()).collect::<Vec<_>>(),
        ["z", "a", "z"]
    );
    assert_eq!(words[2].markdown(), "# z\n---\n`n` last");
}
