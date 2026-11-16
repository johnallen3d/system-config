# Xcode comes from the App Store via mas (homebrew/mas.nix): nixpkgs'
# darwin.xcode needs a manually downloaded .xip. Once it is installed, select
# it, accept the license, run first-launch setup, and fetch the iOS Simulator
# runtime. Runs after Homebrew/mas (postActivation) and is idempotent.
{config, ...}: {
  system.activationScripts.postActivation.text = ''
    xcode_dev=/Applications/Xcode.app/Contents/Developer
    if [ -d "$xcode_dev" ]; then
      echo "configuring Xcode..." >&2
      if [ "$(/usr/bin/xcode-select -p 2>/dev/null)" != "$xcode_dev" ]; then
        /usr/bin/xcode-select --switch "$xcode_dev"
      fi
      xcodebuild="$xcode_dev/usr/bin/xcodebuild"
      if ! "$xcodebuild" -license check >/dev/null 2>&1; then
        "$xcodebuild" -license accept
      fi
      if ! "$xcodebuild" -checkFirstLaunchStatus >/dev/null 2>&1; then
        "$xcodebuild" -runFirstLaunch
      fi
      if ! /usr/bin/sudo -u ${config.system.primaryUser} /usr/bin/xcrun simctl list runtimes iOS 2>/dev/null | grep -q '^iOS'; then
        /usr/bin/sudo -u ${config.system.primaryUser} "$xcodebuild" -downloadPlatform iOS \
          || echo "warning: iOS Simulator runtime download failed" >&2
      fi
    else
      echo "warning: Xcode not installed; skipping Xcode setup" >&2
    fi
  '';
}
