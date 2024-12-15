{...}: {
  security = {
    pam = {
      # allow biometric when password required for `sudo`!!!! 😁
      enableSudoTouchIdAuth = true;
    };
  };

  # services = {karabiner-elements = {enable = true;};};

  system = {
    activationScripts.postUserActivation.text = ''
      # Following line should allow us to avoid a logout/login cycle
      /System/Library/PrivateFrameworks/SystemAdministration.framework/Resources/activateSettings -u
    '';

    defaults = {
      ".GlobalPreferences" = {
        "com.apple.mouse.scaling" = 1.5;
      };

      NSGlobalDomain = {
        AppleICUForce24HourTime = true;
        AppleInterfaceStyle = "Dark";
        AppleInterfaceStyleSwitchesAutomatically = false;
        AppleMeasurementUnits = "Inches";
        AppleScrollerPagingBehavior = true;
        AppleShowAllExtensions = true;
        AppleShowAllFiles = true;
        InitialKeyRepeat = 25;
        KeyRepeat = 4;
        NSAutomaticDashSubstitutionEnabled = true;
        NSAutomaticQuoteSubstitutionEnabled = false;
        NSAutomaticWindowAnimationsEnabled = false;
        NSDocumentSaveNewDocumentsToCloud = false;
        NSNavPanelExpandedStateForSaveMode = true;
        NSNavPanelExpandedStateForSaveMode2 = true;
        NSTableViewDefaultSizeMode = 2;
        NSUseAnimatedFocusRing = false;
        NSWindowResizeTime = 0.001;
        PMPrintingExpandedStateForPrint = true;
        PMPrintingExpandedStateForPrint2 = true;
        _HIHideMenuBar = true;
        "com.apple.keyboard.fnState" = true;
        "com.apple.mouse.tapBehavior" = 1;
        "com.apple.sound.beep.feedback" = 0;
        "com.apple.sound.beep.volume" = 0.75;
        "com.apple.springing.delay" = 0.75;
        "com.apple.springing.enabled" = true;
      };

      dock = {
        autohide = true;
        autohide-delay = 0.01;
        autohide-time-modifier = 0.01;
        dashboard-in-overlay = false;
        expose-animation-duration = 0.01;
        launchanim = false;
        mouse-over-hilite-stack = false;
        mru-spaces = false;
        orientation = "bottom";
        show-process-indicators = false;
        show-recents = false;
        showhidden = true;
        static-only = true;
        tilesize = 24;
        # disable hot corners
        wvous-bl-corner = 1;
        wvous-br-corner = 1;
        wvous-tl-corner = 1;
        wvous-tr-corner = 1;
      };

      finder = {
        AppleShowAllExtensions = true;
        CreateDesktop = false;
        FXDefaultSearchScope = "SCcf";
        FXEnableExtensionChangeWarning = false;
        FXPreferredViewStyle = "clmv";
        QuitMenuItem = true;
        ShowPathbar = true;
        _FXShowPosixPathInTitle = true;
      };

      loginwindow = {
        GuestEnabled = false;
        LoginwindowText = "";
        PowerOffDisabledWhileLoggedIn = true;
        RestartDisabled = true;
        RestartDisabledWhileLoggedIn = true;
        SHOWFULLNAME = true;
        ShutDownDisabled = true;
        ShutDownDisabledWhileLoggedIn = true;
        SleepDisabled = true;
      };

      menuExtraClock = {
        IsAnalog = true;
        Show24Hour = true;
        ShowAMPM = false;
        ShowDate = 0;
      };

      screensaver = {
        askForPassword = true;
        askForPasswordDelay = 10; # seconds
      };

      spaces = {spans-displays = true;};

      trackpad = {
        Clicking = true;
        Dragging = true;
        TrackpadRightClick = true;
      };

      # if error: "Could not write domain com.apple.universalaccess"
      # see this comment
      # https://github.com/mathiasbynens/dotfiles/issues/820#issuecomment-498324762
      # eg.enable for kitty
      # universalaccess = {
      #   closeViewScrollWheelToggle = true;
      #   closeViewZoomFollowsFocus = true;
      #   mouseDriverCursorSize = 1.2;
      #   reduceMotion = true;
      #   reduceTransparency = true;
      # };

      # https://medium.com/@zmre/nix-darwin-quick-tip-activate-your-preferences-f69942a93236
      CustomUserPreferences = {
        "com.apple.desktopservices" = {
          # Avoid creating .DS_Store files on network or USB volumes
          DSDontWriteNetworkStores = true;
          DSDontWriteUSBStores = true;
        };
        "com.apple.AdLib" = {
          allowApplePersonalizedAdvertising = false;
        };
        "com.apple.print.PrintingPrefs" = {
          # Automatically quit printer app once the print jobs complete
          "Quit When Finished" = true;
        };
        "com.apple.SoftwareUpdate" = {
          AutomaticCheckEnabled = true;
          # Check for software updates daily, not just once per week
          ScheduleFrequency = 1;
          # Download newly available updates in background
          AutomaticDownload = 1;
          # Install System data files & security updates
          CriticalUpdateInstall = 1;
        };
        # Prevent Photos from opening automatically when devices are plugged in
        "com.apple.ImageCapture".disableHotPlug = true;
        # Turn on app auto-update
        "com.apple.commerce".AutoUpdate = true;
      };
    };

    keyboard = {
      enableKeyMapping = true;
      remapCapsLockToEscape = true;
    };
  };
}
