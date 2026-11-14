{pkgs}:
pkgs.buildGoModule {
  pname = "fizzy-tui";
  version = "0-unstable-2026-01-29";

  # Upstream has no tags; pin a commit.
  src = pkgs.fetchgit {
    url = "https://codeberg.org/aar0naut/fizzy-tui.git";
    rev = "39f0bfcb24f3f7b9e37a9c09bd110cb3edceda6d";
    hash = "sha256-OTyH9Ay5LL81Vy0XSysfbtFcJoE8uG9qKy7rGuucvxU=";
  };

  # fizzy CLI 4.x wraps responses in {"ok": ...}; upstream still reads "success".
  postPatch = ''
    substituteInPlace internal/fizzy/client.go \
      --replace-fail 'json:"success"' 'json:"ok"'
  '';

  vendorHash ="sha256-fwld+5KAVNSFdwc6VmS/BnMZ11GzWhSI7d6mC+4IDqw=";
  ldflags = ["-s" "-w"];

  meta = with pkgs.lib; {
    description = "Terminal UI for Fizzy boards (needs an authenticated fizzy CLI)";
    homepage = "https://codeberg.org/aar0naut/fizzy-tui";
    license = licenses.mit;
    mainProgram = "fizzy-tui";
  };
}
