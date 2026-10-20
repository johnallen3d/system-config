{pkgs}: let
  lib = pkgs.lib;
  # PaddlePaddle wheels do not support the default Python 3.14 yet.
  python = pkgs.python313.override {
    packageOverrides = final: prev: {
      paddleocr = prev.paddleocr.overrideAttrs (old: {
        # Paddle 3.3's oneDNN/PIR path fails on CPU with PP-OCRv5 models.
        # Use the working CPU engine by default; callers can still opt in.
        postPatch =
          (old.postPatch or "")
          + ''
            substituteInPlace paddleocr/_constants.py \
              --replace-fail 'DEFAULT_ENABLE_MKLDNN = True' 'DEFAULT_ENABLE_MKLDNN = False'
          '';
      });
      # nixpkgs packages PaddleX's base dependencies, but OCR needs this extra.
      paddlex = prev.paddlex.overridePythonAttrs (old: {
        dependencies =
          (old.dependencies or [])
          ++ (with final; [
            imagesize
            opencv-contrib-python
            pyclipper
            pypdfium2
            python-bidi
            shapely
          ]);
        pythonRelaxDeps = (old.pythonRelaxDeps or []) ++ ["opencv-contrib-python"];
      });
      modelscope = prev.modelscope.overrideAttrs (old: {
        # CVE-2026-84202: model YAML must not construct arbitrary Python objects.
        # Keep this fix local to the OCR dependency graph, not a global allowlist.
        postPatch =
          (old.postPatch or "")
          + ''
            substituteInPlace \
              modelscope/models/audio/tts/voice.py \
              modelscope/models/multi_modal/mplug/configuration_mplug.py \
              --replace-fail 'Loader=yaml.Loader' 'Loader=yaml.SafeLoader'
          '';
        meta =
          old.meta
          // {
            knownVulnerabilities =
              lib.filter
              (issue: issue != "CVE-2026-84202: Unsafe YAML Deserialization in Model Config Loading")
              (old.meta.knownVulnerabilities or []);
          };
      });
    };
  };
in
  python.pkgs.paddleocr
