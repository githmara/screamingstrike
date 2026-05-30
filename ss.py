# -*- coding: utf-8 -*-
# Screaming Strike startup file
# Copyright (C) 2019 Yukio Nozawa <personal@nyanchangames.com>
# License: GPL V2.0 (See copying.txt for details)
# See SsAppMain.py for application entry point
import sys
import shutil
import os
import platform_utils.paths
import traceback
if platform_utils.paths.is_mac and platform_utils.paths.is_frozen():
    os.chdir(platform_utils.paths.embedded_data_path())
if platform_utils.paths.is_windows:
    genpy_path = os.path.join(os.environ["temp"], "gen_py")
    if os.path.isdir(genpy_path):
        shutil.rmtree(genpy_path)
    # end rebuilding
# end win
import buildSettings
from ssAppMain import *


def loadDotEnv(path=".env"):
    """Minimal, dependency-free .env loader.

    Sets os.environ[KEY] = VALUE for each KEY=VALUE line (only when KEY is not already in the
    environment). Used for diagnostic flags such as SS_REALTIME_LOG in frozen builds, where setting
    a real environment variable is awkward: just drop a .env next to the executable. A missing or
    malformed file is silently ignored. Not shipped with releases.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def main():
    loadDotEnv()
    app = ssAppMain()
    app.initialize()
    app.run()


def exchandler(type, exc, tb):
    f = open("data/errorLog.txt", "w")
    f.writelines(traceback.format_exception(type, exc, tb))
    f.close()
    dialog.dialog("Error", "An error occured. Please send error-log.txt, found in the data directory of wherever you are running the game, to the developer.")
    sys.exit()


#global schope
sys.excepthook = exchandler
if __name__ == "__main__":
    main()
