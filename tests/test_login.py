"""GUI login: isolated CLI profile, staged verification, cancellation and rollback."""
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support
from felismusic_gui import login


BROWSER=dict(id='test',name='Test browser',engine='firefox',launcher='native',cookie_browser='firefox')


class Manager:
    AUTH_FORMAT_VERSION=1
    def __init__(self,root):
        self.cookie_file=str(root/'cookies.txt');self.state_file=str(root/'auth-state.json')
        self.profiles_dir=str(root/'auth-profiles')
        Path(self.profiles_dir).mkdir()
        (Path(self.profiles_dir)/'profile-cookie').write_text('ISOLATED_BROWSER_SECRET')
        self.slow=False;self.missing=False;self.none=False
    def detect_browsers(self):return [] if self.none else [dict(BROWSER)]
    def _ensure_profile_permissions(self,browser):pass
    def _launch_command(self,browser):
        if self.missing:return ['/nonexistent/felis-test-browser']
        return [sys.executable,'-c','import time; time.sleep(20)' if self.slow else 'pass']
    def _extract_cookies(self,browser):Path(self.cookie_file).write_text('NEW_COOKIE_SECRET')
    def _write_json_private(self,path,value):Path(path).write_text(json.dumps(value));os.chmod(path,0o600)
    def _user_agent(self,browser=None):return 'Test agent'
    def ytmusic_headers(self):return {'Cookie':Path(self.cookie_file).read_text()}
    def yt_dlp_http_headers(self):return {}
    def session_exists(self):return Path(self.cookie_file).exists()


class LoginTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.storage=tempfile.TemporaryDirectory();self.addCleanup(self.storage.cleanup)
        self.root=Path(self.storage.name);self.manager=Manager(self.root)
        Path(self.manager.cookie_file).write_text('OLD_COOKIE_SECRET');Path(self.manager.state_file).write_text('OLD_STATE')
        self.original=(Path(self.manager.cookie_file).read_bytes(),Path(self.manager.state_file).read_bytes())
        self.api=Mock();self.api.get_account_info.return_value={'accountName':'Verified account'}
        self.legacy=self.root/'browser.json';self.legacy.write_text('LEGACY_SECRET')
        for p in [patch.object(support.core,'AUTH',self.manager),patch.object(login,'YTMusic',return_value=self.api),
                  patch.object(support.core,'LEGACY_AUTH_FILE',str(self.legacy))]:
            p.start();self.addCleanup(p.stop)
        self.old=Mock();self.b._ytmusic=self.old;self.b._set_connected(True)

    def unchanged(self):
        self.assertEqual((Path(self.manager.cookie_file).read_bytes(),Path(self.manager.state_file).read_bytes()),self.original)

    def browser(self):
        self.assertTrue(self.b.openLogin());self.until(lambda:self.b.loginState['phase'] in ('choose','error'))
        self.assertEqual(self.b.loginState['browsers'],[{'id':'test','name':'Test browser'}])
        self.assertTrue(self.b.startLogin('test'));self.until(lambda:self.b.loginState.get('canFinish',False))

    def test_login_publishes_only_verified_account_and_resets_old_views(self):
        self.b._library_items_model.set_items([dict(kind='playlist',playlistId='PLold')])
        self.b._detail_meta=dict(kind='playlist',playlistId='PLold');self.b._detail_title='Old account'
        self.b._deleted_playlists={'PLdeleted'};self.b._pending_created_playlists={'PLpending':{}}
        initialized=[];self.b.initialized.connect(lambda:initialized.append(not self.b.busy))
        self.browser();self.unchanged();self.api.get_account_info.assert_not_called()
        self.assertFalse(self.b.openLogin());self.assertFalse(self.b.startLogin('test'))
        self.assertTrue(self.b.finishLogin());self.assertFalse(self.b.finishLogin())
        self.until(lambda:self.b.loginState['phase']=='success')
        self.assertEqual(Path(self.manager.cookie_file).read_text(),'NEW_COOKIE_SECRET')
        self.assertEqual(Path(self.manager.cookie_file).stat().st_mode&0o777,0o600)
        self.assertEqual(Path(self.manager.state_file).stat().st_mode&0o777,0o600)
        self.assertEqual(json.loads(Path(self.manager.state_file).read_text())['browser_id'],'test')
        self.assertEqual(self.b.accountName,'Verified account');self.assertTrue(self.b.connected)
        self.assertEqual(initialized,[True]);self.assertIs(self.b._ytmusic,self.api)
        self.assertFalse(self.b._library_items_model.snapshot());self.assertFalse(self.b._detail_meta)
        self.assertFalse(self.b._deleted_playlists);self.assertFalse(self.b._pending_created_playlists)
        self.assertFalse(self.played);self.assertFalse(self.b.playerHasTrack)
        self.assertFalse(list(self.root.glob('.gui-login-*')))

    def test_cancel_browser_preserves_active_client_and_files(self):
        self.manager.slow=True
        self.assertTrue(self.b.openLogin());self.until(lambda:self.b.loginState['phase']=='choose')
        self.b.startLogin('test');self.until(lambda:self.b._login_process.state()==support.backend.QProcess.ProcessState.Running)
        self.assertFalse(self.b.finishLogin());self.b.cancelLogin()
        self.until(lambda:self.b._login_process.state()==support.backend.QProcess.ProcessState.NotRunning)
        self.unchanged();self.assertIs(self.b._ytmusic,self.old);self.assertTrue(self.b.connected)
        self.assertFalse(self.b.busy);self.assertEqual(self.b.loginState['phase'],'closed')
        self.api.get_account_info.assert_not_called()

    def test_cancel_during_verification_ignores_late_result_and_removes_staging(self):
        self.browser();entered=Event()
        def blocked(**kwargs):entered.set();self.release.wait(3);return []
        self.api.get_library_playlists.side_effect=blocked
        self.b.finishLogin();self.until(entered.is_set);self.b.cancelLogin();self.release.set()
        self.until(lambda:not list(self.root.glob('.gui-login-*')))
        self.unchanged();self.assertIs(self.b._ytmusic,self.old);self.assertFalse(self.b.busy)
        self.assertEqual(self.b.loginState['phase'],'closed')

    def test_verification_error_keeps_old_credentials_and_never_displays_secret_exception(self):
        self.browser();self.api.get_library_playlists.side_effect=RuntimeError('PRIVATE_COOKIE_RESPONSE')
        self.b.finishLogin();self.until(lambda:self.b.loginState['phase']=='error')
        self.unchanged();self.assertNotIn('PRIVATE',self.b.loginState['message'])
        self.assertIs(self.b._ytmusic,self.old);self.assertTrue(self.b.connected)
        self.assertFalse(list(self.root.glob('.gui-login-*')));self.b.cancelLogin()

    def test_no_browser_and_failed_launch_can_be_cancelled_or_retried(self):
        self.manager.none=True;self.b.openLogin();self.until(lambda:self.b.loginState['phase']=='error')
        self.assertFalse(self.b.startLogin('test'));self.b.cancelLogin();self.manager.none=False
        self.manager.missing=True;self.b.openLogin();self.until(lambda:self.b.loginState['phase']=='choose')
        self.b.startLogin('test');self.until(lambda:self.b.loginState['phase']=='error');self.unchanged()
        self.manager.missing=False;self.assertTrue(self.b.startLogin('test'))
        self.until(lambda:self.b.loginState.get('canFinish',False));self.b.cancelLogin()

    def test_publish_failure_rolls_back_both_files(self):
        candidate=login.LoginCandidate(self.manager,BROWSER);self.addCleanup(candidate.close);candidate.verify()
        original_replace=login.os.replace;calls=[]
        def replace(source,target):
            calls.append(target)
            if len(calls)==2:raise OSError('simulated second file failure')
            return original_replace(source,target)
        with patch.object(login.os,'replace',side_effect=replace):
            with self.assertRaises(OSError):candidate.publish()
        self.unchanged()

    def test_first_login_with_no_credentials_publishes_verified_account(self):
        Path(self.manager.cookie_file).unlink();Path(self.manager.state_file).unlink()
        self.b._ytmusic=None;self.b._set_connected(False)
        self.browser();self.assertFalse(Path(self.manager.cookie_file).exists())
        self.b.finishLogin();self.until(lambda:self.b.loginState['phase']=='success')
        self.assertTrue(self.b.connected);self.assertEqual(self.b.accountName,'Verified account')
        self.assertEqual(Path(self.manager.cookie_file).read_text(),'NEW_COOKIE_SECRET')

    def test_anonymous_account_response_is_not_accepted_as_a_login(self):
        self.api.get_account_info.return_value={}
        candidate=login.LoginCandidate(self.manager,BROWSER);self.addCleanup(candidate.close)
        with self.assertRaises(ValueError):candidate.verify()
        with self.assertRaises(ValueError):candidate.publish()
        self.unchanged()

    def test_logout_then_first_start_without_account_and_fresh_login(self):
        normal=self.root/'normal-browser';normal.mkdir();(normal/'cookies').write_text('UNTOUCHED')
        self.start('A','B');self.b._library_items_model.set_items([dict(kind='playlist',playlistId='PLold')])
        self.assertTrue(self.b.logout());self.until(lambda:not self.b.busy)
        self.assertFalse(self.b.connected);self.assertIsNone(self.b._ytmusic)
        self.assertFalse(self.b.playerHasTrack);self.assertEqual(self.b.playerState,'idle')
        self.assertFalse(self.b.libraryItemsModel.snapshot());self.assertTrue(self.stops)
        self.assertFalse(Path(self.manager.cookie_file).exists());self.assertFalse(Path(self.manager.state_file).exists())
        self.assertFalse(Path(self.manager.profiles_dir).exists());self.assertFalse(self.legacy.exists())
        self.assertEqual((normal/'cookies').read_text(),'UNTOUCHED')
        self.assertIn('Odhlášeno',self.b.status)
        played=list(self.played);self.b.initialize();self.until(lambda:self.b.loginState['phase']=='choose')
        self.api.get_account_info.assert_not_called();self.assertFalse(self.b.connected)
        self.b.cancelLogin();self.assertFalse(self.b.busy);self.assertEqual(self.played,played)
        self.b.initialize();self.until(lambda:self.b.loginState['phase']=='choose')
        self.b.startLogin('test');self.until(lambda:self.b.loginState.get('canFinish',False))
        self.b.finishLogin();self.until(lambda:self.b.loginState['phase']=='success')
        self.assertTrue(self.b.connected);self.assertEqual(self.played,played)

    def test_partial_logout_failure_is_reported_and_can_be_retried(self):
        with patch.object(login.shutil,'rmtree',side_effect=OSError('profile locked')):
            self.assertTrue(self.b.logout());self.until(lambda:not self.b.busy)
        self.assertFalse(self.b.connected);self.assertTrue(Path(self.manager.profiles_dir).exists())
        self.assertIn('není dokončené',self.b.status);self.assertTrue(self.errors)
        self.assertTrue(self.b.logout());self.until(lambda:not self.b.busy)
        self.assertFalse(Path(self.manager.profiles_dir).exists());self.assertIn('Odhlášeno',self.b.status)

    def test_logout_does_not_follow_profile_symlink(self):
        import shutil
        shutil.rmtree(self.manager.profiles_dir)
        normal=self.root/'normal-profile';normal.mkdir();(normal/'cookie').write_text('UNCHANGED')
        Path(self.manager.profiles_dir).symlink_to(normal,target_is_directory=True)
        login.remove_login(self.manager,self.legacy)
        self.assertEqual((normal/'cookie').read_text(),'UNCHANGED')
        self.assertFalse(Path(self.manager.profiles_dir).is_symlink())

    def test_logout_guards_and_stop_failure_preserve_credentials(self):
        self.b._set_busy(True);self.assertFalse(self.b.logout());self.b._set_busy(False)
        self.b._liked_load_state='loading';self.assertFalse(self.b.logout());self.b._liked_load_state='complete'
        self.start('A','B')
        with patch.object(self.mc,'stop',side_effect=RuntimeError('audio stop failed')):
            self.assertFalse(self.b.logout())
        self.unchanged();self.assertTrue(self.b.connected)

    def test_late_verified_result_after_cancel_is_closed_without_publishing(self):
        self.b.openLogin();self.until(lambda:self.b.loginState['phase']=='choose')
        generation=self.b._login_generation;self.b.cancelLogin();candidate=Mock()
        self.b._apply_login_result(generation,'verified',candidate)
        candidate.close.assert_called_once();candidate.publish.assert_not_called();self.unchanged()

    def test_playback_loading_busy_and_shutdown_guards(self):
        self.start('A','B');self.assertFalse(self.b.openLogin())
        self.b.stopPlayback();self.b._liked_load_state='loading';self.assertFalse(self.b.openLogin())
        self.b._liked_load_state='complete';self.b._set_busy(True);self.assertFalse(self.b.openLogin())
        self.b._set_busy(False);self.b.shutdown();self.assertFalse(self.b.openLogin())
        self.unchanged()
