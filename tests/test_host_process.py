"""Frozen browser processes use host libraries; app and Deno retain bundled ones."""
import os
import sys
from unittest import TestCase
from unittest.mock import patch
import test_prefetch
from felismusic_gui import host_process


class HostProcessTests(TestCase):
    def test_unfrozen_environment_is_unchanged_and_returns_a_copy(self):
        with patch.object(host_process, '_host_environment', None), patch.dict(
                os.environ, {'LD_LIBRARY_PATH': '/custom', 'PATH': '/usr/bin'}, clear=True):
            host_process.capture_host_environment()
            result = host_process.host_environment()
            self.assertEqual(result, dict(os.environ))
            result['PATH'] = 'changed'
            self.assertEqual(os.environ['PATH'], '/usr/bin')

    def test_frozen_original_library_and_executable_paths_are_restored_for_browser_only(self):
        env = {'LD_LIBRARY_PATH': '/bundle:/custom', 'LD_LIBRARY_PATH_ORIG': '/custom',
            'PATH': '/app/usr/bin:/usr/bin', 'FELISMUSIC_HOST_PATH': '/usr/bin',
            'WAYLAND_DISPLAY': 'wayland-0', 'DBUS_SESSION_BUS_ADDRESS': 'session', 'HOME': '/home/user'}
        with patch.object(host_process, '_host_environment', None), patch.object(
                sys, 'frozen', True, create=True), patch.dict(os.environ, env, clear=True):
            host_process.capture_host_environment()
            # Later Qt/GI hooks may overwrite paths in the app, never in browsers.
            os.environ['QT_PLUGIN_PATH'] = '/bundle/qt'
            os.environ['GI_TYPELIB_PATH'] = '/bundle/gi'
            child = host_process.host_environment()
            self.assertEqual(child['LD_LIBRARY_PATH'], '/custom')
            self.assertEqual(child['PATH'], '/usr/bin')
            self.assertEqual(child['WAYLAND_DISPLAY'], 'wayland-0')
            self.assertEqual(child['DBUS_SESSION_BUS_ADDRESS'], 'session')
            self.assertNotIn('QT_PLUGIN_PATH', child)
            self.assertNotIn('GI_TYPELIB_PATH', child)
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/bundle:/custom')
            self.assertEqual(os.environ['PATH'], '/app/usr/bin:/usr/bin')
            child.clear()
            self.assertEqual(host_process.host_environment()['HOME'], '/home/user')

    def test_frozen_with_no_original_library_path_removes_bundle_path(self):
        with patch.object(host_process, '_host_environment', None), patch.object(
                sys, 'frozen', True, create=True), patch.dict(
                os.environ, {'LD_LIBRARY_PATH': '/bundle'}, clear=True):
            host_process.capture_host_environment()
            self.assertNotIn('LD_LIBRARY_PATH', host_process.host_environment())
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/bundle')
