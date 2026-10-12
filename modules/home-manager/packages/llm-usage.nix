{pkgs}:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "llm-usage";
  version = "2026-10-10";

  src = pkgs.fetchFromGitHub {
    owner = "amfaro";
    repo = "llm-usage";
    rev = "85d68db21e011820a3c1233eb4b067c9b1e8e1c0";
    hash = "sha256-UFF3qkwo2G76GlRk+kVW+TY1XUH5uiSzxw0dJ6X/HbQ=";
  };

  cargoHash = "sha256-V8pi/ktfhQcDV6PmSGWKBhDb9t3sWB5LmnNU8ZIF+f4=";

  postPatch = ''
    substituteInPlace src/main.rs \
      --replace-fail \
        'const CLAUDE_CODE_CACHE_MAX_AGE: u64 = 60 * 60;' \
        'const CLAUDE_CODE_CACHE_MAX_AGE: u64 = u64::MAX;' \
      --replace-fail \
        'fn claude_code_cache_is_durable_sanitized_and_expires_after_one_hour()' \
        'fn claude_code_cache_is_durable_sanitized_and_does_not_expire()' \
      --replace-fail \
        'assert!(cached_claude_code_usage(&loaded, 4_601, "stale").is_none());' \
        'assert!(cached_claude_code_usage(&loaded, 4_601, "stale").is_some());'

    # Proxy snapshots share the patched local-cache helper. Keep their upstream
    # one-hour expiry instead of making remote stale data durable as well.
    substituteInPlace src/cliproxy.rs \
      --replace-fail \
        '    let mut usage = cached_claude_code_usage(cache, fetched_at, message)?;' \
        '    if fetched_at.saturating_sub(cache.fetched_at) > 60 * 60 { return None; }
    let mut usage = cached_claude_code_usage(cache, fetched_at, message)?;'
  '';

  meta = {
    description = "Subscription quota dashboard for Codex, OpenCode Go, and Claude Code";
    mainProgram = "llm-usage";
  };
}
