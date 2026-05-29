{mkPiExtension, ...}: {
  tokyonight-moon = {
    pkg = mkPiExtension {
      pname = "@juanibiapina/pi-tokyonight";
      version = "1.0.1";
      url = "https://registry.npmjs.org/@juanibiapina/pi-tokyonight/-/pi-tokyonight-1.0.1.tgz";
      hash = "sha256-14x1y8s748j+sdPkXc+0ehnBuKAIufA4OWm4pcGCaI0=";
      npmDepsHash = "sha256-5wJzqL6oSfNLteXIj4VwJYP5a2IzeDTlDDvpQxhqNYI=";
      lockfile = ../packages/pi-tokyonight-package-lock.json;
      description = "Tokyo Night Moon theme for pi coding agent";
      homepage = "https://github.com/juanibiapina/pi-tokyonight";
      forceEmptyCache = true;
    };
    file = "tokyonight-moon.json";
  };
}
