# Temporary overlay to bypass broken nokogiri dependency chain for actionlint
# Remove once nokogiri / ronn build fixed upstream (post Oct 2025)
(final: prev: {
  actionlint = prev.actionlint.overrideAttrs (old: {
    # The upstream derivation builds the Go binary, then uses ronn (ruby/nokogiri) to build the man page.
    # We skip the man page generation to avoid pulling in ruby->nokogiri which is currently broken on Darwin.
    nativeBuildInputs = with prev; builtins.filter (p: false) old.nativeBuildInputs; # clear
    buildInputs = with prev; builtins.filter (p: false) (old.buildInputs or []); # clear
    patches = [];
    postPatch = ''
      echo "Skipping man page generation for actionlint (temporary overlay)" >&2
    '';
    # Keep original buildPhase that compiles Go; it's in old.buildPhase or default.
    # Ensure installPhase just installs the binary if it exists.
    installPhase = ''
      runHook preInstall
      mkdir -p $out/bin
      # The build produces actionlint in $GOPATH/bin or via go build . ; ensure we build explicitly
      echo "Building actionlint without man page" >&2
      go build -o actionlint .
      install -m755 actionlint $out/bin/
      runHook postInstall
    '';
    # Avoid references to man output
    outputs = [ "out" ];
    meta = old.meta // {
      description = (old.meta.description or "") + " (without man page; temporary nokogiri workaround)";
      # add a temporary broken reason reference
      broken = false;
    };
  });
})
