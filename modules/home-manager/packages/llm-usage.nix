{pkgs}:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "llm-usage";
  version = "2026-08-19";

  src = pkgs.fetchFromGitHub {
    owner = "amfaro";
    repo = "llm-usage";
    rev = "0642e52c13d531a9b73d8fb3992eab01651017db";
    hash = "sha256-Q7n0yjMHHHImNZ/vyDHa3sYPj+lwU/npqsflk+PCT9s=";
  };

  cargoHash = "sha256-YN0KXQXpRd8Nr5edmswGoCw9qEQ1EjZA5xy+pSz/nJ0=";

  meta = {
    description = "Subscription quota dashboard for Codex, OpenCode Go, and Claude Code";
    mainProgram = "llm-usage";
  };
}
