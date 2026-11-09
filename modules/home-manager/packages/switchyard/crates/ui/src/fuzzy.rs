//! Fuzzy matching over several fields of a row at once.

use nucleo_matcher::pattern::Pattern;
use nucleo_matcher::{Matcher, Utf32Str};

/// Score `fields` against `pattern` as one haystack, which keeps multi-word
/// queries working across fields, and split the hit positions back out per
/// field (character indices within each).
pub fn score_fields(matcher: &mut Matcher, pattern: &Pattern, fields: &[&str]) -> Option<(u32, Vec<Vec<usize>>)> {
    let hay = fields.join("  ");
    let mut buf = Vec::new();
    let score = pattern.score(Utf32Str::new(&hay, &mut buf), matcher)?;
    let mut idx = Vec::new();
    pattern.indices(Utf32Str::new(&hay, &mut buf), matcher, &mut idx);
    idx.sort_unstable();
    idx.dedup();
    let mut per_field = Vec::new();
    let mut start = 0usize;
    for f in fields {
        let len = f.chars().count();
        per_field.push(
            idx.iter()
                .map(|&i| i as usize)
                .filter(|&i| i >= start && i < start + len)
                .map(|i| i - start)
                .collect(),
        );
        start += len + 2;
    }
    Some((score, per_field))
}
