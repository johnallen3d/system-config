//! Work names. Naming follows the old herdr short-name convention: `api-work`
//! becomes branch `feature/api-work` in `.worktrees/api-work` with tab
//! `api-work`; a name with a slash is used as the branch as is, its slug
//! replacing `/` with `-`.

/// The agent harnesses work can run in; the first is the default.
pub const HARNESSES: [&str; 2] = ["claude", "pi"];

/// Normalise typed input: lowercase, spaces become dashes, and only
/// characters that are safe in a branch, a path and a tab label survive.
pub fn name_char(c: char) -> Option<char> {
    match c {
        ' ' | '_' => Some('-'),
        'A'..='Z' => Some(c.to_ascii_lowercase()),
        'a'..='z' | '0'..='9' | '-' | '.' | '/' => Some(c),
        _ => None,
    }
}

/// Why a name can't be used yet, or None when it can.
pub fn name_problem(name: &str) -> Option<&'static str> {
    if name.is_empty() {
        return Some("name the work");
    }
    if name.starts_with(['/', '-', '.']) || name.ends_with(['/', '.']) || name.contains("//") || name.contains("..") {
        return Some("not a valid branch name");
    }
    None
}

/// (branch, slug) for a work name.
pub fn branch_and_slug(name: &str) -> (String, String) {
    if name.contains('/') {
        (name.to_string(), name.replace('/', "-"))
    } else {
        (format!("feature/{name}"), name.to_string())
    }
}
