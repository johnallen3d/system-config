{mkPiExtension, ...}: {
  tokyo-night-storm = {
    pkg = mkPiExtension {
      pname = "pi-tokyo-night-storm";
      version = "1.0.0";
      hash = "sha256-CwRmlhMlIeEJN8D0tQ+S6TGVbPBBJEWZs5jUxfE6QPY=";
      npmDepsHash = "sha256-Aeyt2zVmx1UpOVZ8T8dRWRPf9uu+Pau8fKkAxWf6tDQ=";
      lockfile = ../packages/pi-tokyo-night-storm-package-lock.json;
      description = "Tokyo Night Storm theme for pi coding agent";
      homepage = "https://github.com/sanathks/pi-tokyo-night-storm";
      forceEmptyCache = true;
    };
    file = "tokyo-night-storm.json";
  };
}
