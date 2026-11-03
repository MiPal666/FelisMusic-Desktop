"""Use the CLI's isolated browser profile, staging credentials until verified."""
from copy import copy
from pathlib import Path
import os
import shutil
import tempfile
import time

from PySide6.QtCore import QCoreApplication
from ytmusicapi import YTMusic
from .diagnostics import instrument_ytmusic


def remove_login(manager, legacy_file):
    """Remove only FelisMusic's saved credentials and isolated browser profiles."""
    failed = False
    for name in (manager.cookie_file, manager.state_file, legacy_file):
        try:
            Path(name).unlink(missing_ok=True)
        except OSError:
            failed = True
    try:
        profiles = Path(manager.profiles_dir)
        if profiles.is_symlink():
            profiles.unlink()
        elif profiles.exists():
            shutil.rmtree(profiles)
    except OSError:
        failed = True
    if failed:
        raise RuntimeError(QCoreApplication.translate("Login", "Uložené přihlášení se nepodařilo celé odstranit. Zavři přihlašovací okno prohlížeče a zkus odhlášení znovu."))


class LoginCandidate:
    def __init__(self, manager, browser):
        self.original = manager
        self.directory = tempfile.TemporaryDirectory(prefix='.gui-login-', dir=Path(manager.cookie_file).parent)
        self.manager = copy(manager)
        self.manager.cookie_file = str(Path(self.directory.name) / 'cookies.txt')
        self.manager.state_file = str(Path(self.directory.name) / 'auth-state.json')
        self.browser = browser
        self.result = None

    def verify(self):
        manager, browser = self.manager, self.browser
        manager._extract_cookies(browser)
        manager._write_json_private(manager.state_file, dict(
            format=manager.AUTH_FORMAT_VERSION, browser_id=browser['id'], browser_name=browser['name'],
            launcher=browser['launcher'], flatpak_id=browser.get('flatpak_id'),
            user_agent=manager._user_agent(browser), updated_at=int(time.time())))
        headers = manager.ytmusic_headers()
        api = instrument_ytmusic(YTMusic(headers))
        api.get_library_playlists(limit=1)
        account = api.get_account_info()
        if not isinstance(account, dict) or not account.get('accountName'):
            raise ValueError('Account not confirmed')
        self.result = dict(ytmusic=api, account=account, auth_headers=headers)

    def publish(self):
        if self.result is None:
            raise ValueError('Unverified login')
        pairs = [(self.manager.cookie_file, self.original.cookie_file),
                 (self.manager.state_file, self.original.state_file)]
        backups = {}
        changed = []
        # Prepare both backups before modifying either live file.
        for i, (_, target) in enumerate(pairs):
            if Path(target).exists():
                backup = str(Path(self.directory.name) / f'previous-{i}')
                shutil.copyfile(target, backup)
                os.chmod(backup, 0o600)
                backups[target] = backup
        try:
            for source, target in pairs:
                os.chmod(source, 0o600)
                os.replace(source, target)
                changed.append(target)
        except Exception:
            for target in reversed(changed):
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    Path(target).unlink(missing_ok=True)
            raise
        return self.result

    def close(self):
        self.directory.cleanup()
