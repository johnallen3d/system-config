{pkgs}:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "llm-usage";
  version = "2026-11-23";

  src = pkgs.fetchFromGitHub {
    owner = "amfaro";
    repo = "llm-usage";
    rev = "6752e46a0d7ef47cd8c07de3103938e771e370bf";
    hash = "sha256-PM8cXTECJcvTc/Ws/YsBDXx/F+sf+Qiyn4qTYbFk+HE=";
  };

  cargoHash = "sha256-mPpEMITx+3g5cc63suNdCil2jeyUzz3qr1Vdza+55zo=";

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
    description = "Subscription quota dashboard for Codex, OpenCode Go, Claude Code, and Gemini";
    mainProgram = "llm-usage";
  };
}
