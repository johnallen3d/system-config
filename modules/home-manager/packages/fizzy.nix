{pkgs}:
# Not in nixpkgs. Nix-installed so launchd/systemd services (switchyard-server)
# find it on the per-user profile PATH, which lacks /opt/homebrew/bin.
pkgs.buildGoModule rec {
  pname = "fizzy";
  version = "4.1.0";

  src = pkgs.fetchFromGitHub {
    owner = "basecamp";
    repo = "fizzy-cli";
    rev = "v${version}";
    hash = "sha256-ZIhSWc/7QgPMiosEia/f72URGWxD5XTzbgRjAZHmXZU=";
  };

  vendorHash = "sha256-feihI0cJ9MZGz2b/xpr0pf4LRmZXzVRECUAVlh2xYPs=";
  subPackages = ["cmd/fizzy"];
  env.CGO_ENABLED = 0;
  ldflags = ["-s" "-w" "-X main.version=${version}"];
  # Upstream tests include e2e suites that need the network.
  doCheck = false;

  nativeBuildInputs = [pkgs.installShellFiles];
  postInstall = ''
    installShellCompletion --cmd fizzy \
      --bash <($out/bin/fizzy completion bash) \
      --fish <($out/bin/fizzy completion fish) \
      --zsh <($out/bin/fizzy completion zsh)
  '';

  meta = with pkgs.lib; {
    description = "CLI for managing Fizzy boards, cards, and tasks";
    homepage = "https://github.com/basecamp/fizzy-cli";
    license = licenses.mit;
    mainProgram = "fizzy";
  };
}
