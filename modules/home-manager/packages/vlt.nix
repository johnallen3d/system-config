{pkgs}:
pkgs.buildGoModule rec {
  pname = "vlt";
  version = "0.11.0";

  src = pkgs.fetchFromGitHub {
    owner = "paivot-ai";
    repo = "vlt";
    rev = "v${version}";
    hash = "sha256-zBx/Xn+ILwkoda9NSDUIgzn2Gi0EB1t5V1/ObDRHFxc=";
  };

  vendorHash = null;
  subPackages = ["cmd/vlt"];
  ldflags = [
    "-s"
    "-w"
    "-X main.version=${version}"
  ];

  meta = with pkgs.lib; {
    description = "Fast, standalone CLI for Obsidian vault operations";
    homepage = "https://github.com/paivot-ai/vlt";
    license = licenses.mit;
    mainProgram = "vlt";
  };
}
