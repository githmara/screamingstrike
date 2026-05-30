# -*- coding: utf-8 -*-
# Screaming Strike build settings
# Copyright (C) 2019 Yukio Nozawa <personal@nyanchangames.com>
# License: GPL V2.0 (See copying.txt for details)
import scorePostingAdapter
import scoreViewAdapter

#	sys.stderr = open('data/stderr.txt', 'w') # uncomment this line when releasing

GAME_NAME = "Screaming Strike 2"
# Numeric version, kept as a float because the changelog / update logic does float() and "%.2f" on it.
GAME_VERSION = 2.08
# Human-facing version label for this unofficial fork. Used only for display (window title), so it can
# carry the "-fork" suffix without breaking the numeric GAME_VERSION logic.
GAME_VERSION_STRING = "2.08-fork"
# Specify the path to the updateChecker.php, leave it blank to disable update checking
UPDATE_SERVER_ADDRESS = ""
# Specify win and mac installer remote paths, leave them blank to disable
UPDATE_PACKAGE_URL = {
    "Windows": "",
    "Darwin": ""
}
# Local filename to be downloaded. If the above option is specified, you must specify below, too.
UPDATE_PACKAGE_LOCAL_NAME = {
    "Windows": "",
    "Darwin": ""
}

# Specify the default score posting / viewing adapter to use. specify AdapterBase to disable score posting.


def getScorePostingAdapter(): return scorePostingAdapter.AdapterBase()
def getScoreViewAdapter(): return scoreViewAdapter.AdapterBase()
