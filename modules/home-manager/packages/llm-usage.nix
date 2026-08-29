{pkgs}:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "llm-usage";
  version = "2026-08-28";

  src = pkgs.fetchFromGitHub {
    owner = "amfaro";
    repo = "llm-usage";
    rev = "748a70daecfad545449f574c8c0667b26202c0cb";
    hash = "sha256-CsH8x3mKEb9qkaa+VH8+T9v5ikvoe/1tj+dPtK1ZQaY=";
  };

  cargoHash = "sha256-WnS+zWrj20HXozKOHPjzD3plugDqA+n6dPtMs2K6St8=";

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
  '';

  meta = {
    description = "Subscription quota dashboard for Codex, OpenCode Go, and Claude Code";
    mainProgram = "llm-usage";
  };
}
