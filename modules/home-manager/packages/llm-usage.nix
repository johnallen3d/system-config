{pkgs}:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "llm-usage";
  version = "2026-08-21";

  src = pkgs.fetchFromGitHub {
    owner = "amfaro";
    repo = "llm-usage";
    rev = "eaaf4d0bf412eedadc8d2142a72c8ed60cbecafb";
    hash = "sha256-aEKaxx0HxewWhjovIXcmGFRG4stCDjK98qC3KxqwcFI=";
  };

  cargoHash = "sha256-Wbr7mZfL0EtEYXTQdcNBbYEFnlqKWAmK+s3D2Z71NSw=";

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
