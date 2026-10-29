"""Opt-in Cast inventory must never control devices or alter local playback."""
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import test_prefetch as support
from felismusic_gui import cast_discovery as discovery


def info(uuid,name,kind='audio'):
    return SimpleNamespace(uuid=uuid,friendly_name=name,cast_type=kind)


class DiscoveryWorkerTests(unittest.TestCase):
    def test_live_inventory_filters_sorts_keeps_duplicate_names_and_closes_resources(self):
        browser=Mock();browser.devices={1:info('B','Same'),2:info('A','Same','group'),
                                      3:info('TV','TV','cast'),4:info(None,'Missing ID')}
        zc=Mock();settled=Event();updates=[]
        def update(rows,scanning,error):
            updates.append((rows,scanning,error))
            if not scanning:settled.set()
        with patch.object(discovery,'Zeroconf',return_value=zc), \
             patch.object(discovery,'CastBrowser',return_value=browser), \
             patch.object(discovery.CastDiscovery,'initial_settle',.02), \
             patch.object(discovery.CastDiscovery,'refresh_settle',.02), \
             patch.object(discovery.CastDiscovery,'poll_interval',.005), \
             patch.object(support.core.pychromecast,'get_chromecasts') as connect, \
             patch.object(support.core.pychromecast,'get_chromecast_from_cast_info') as controller:
            worker=discovery.CastDiscovery(update);worker.start()
            try:
                self.assertTrue(settled.wait(2));self.assertEqual([x['id'] for x in updates[-1][0]],['A','B'])
                browser.devices={1:info('B','Renamed')};settled.clear();worker.refresh()
                self.assertTrue(settled.wait(2));self.assertEqual(updates[-1][0],[dict(id='B',name='Renamed',kind='audio')])
            finally:
                worker.close();worker.thread.join(2)
            self.assertFalse(worker.thread.is_alive());browser.stop_discovery.assert_called_once()
            zc.close.assert_called_once();connect.assert_not_called();controller.assert_not_called()

    def test_start_error_reports_no_private_details_and_releases_resources(self):
        browser=Mock();browser.start_discovery.side_effect=RuntimeError('PRIVATE_NETWORK_DETAILS')
        zc=Mock();updates=[]
        with patch.object(discovery,'Zeroconf',return_value=zc),patch.object(discovery,'CastBrowser',return_value=browser):
            worker=discovery.CastDiscovery(lambda *args:updates.append(args));worker.start();worker.thread.join(2)
        self.assertFalse(worker.thread.is_alive());self.assertEqual(updates[0][:2],([],False))
        self.assertNotIn('PRIVATE',updates[0][2]);zc.close.assert_called_once();browser.stop_discovery.assert_called_once()

    def test_shutdown_during_initialization_drops_result_and_closes_browser(self):
        entered,release=Event(),Event();browser=Mock();zc=Mock();updates=[]
        def start():entered.set();release.wait(2)
        browser.start_discovery.side_effect=start
        with patch.object(discovery,'Zeroconf',return_value=zc),patch.object(discovery,'CastBrowser',return_value=browser):
            worker=discovery.CastDiscovery(lambda *args:updates.append(args));worker.start()
            self.assertTrue(entered.wait(2));worker.close();release.set();worker.thread.join(2)
        self.assertFalse(updates);browser.stop_discovery.assert_called_once();zc.close.assert_called_once()


class CastInventoryTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.scanner=Mock();self.scanner.thread.is_alive.return_value=True
        p=patch.object(support.backend,'CastDiscovery',return_value=self.scanner)
        self.factory=p.start();self.addCleanup(p.stop)

    def test_no_startup_scan_then_explicit_scan_refresh_and_shutdown(self):
        self.assertEqual(self.b.castState['devices'],[dict(id='local',name='Toto zařízení',kind='local')])
        self.factory.assert_not_called();self.assertTrue(self.b.discoverCastDevices())
        self.scanner.start.assert_called_once();self.assertTrue(self.b.castState['scanning'])
        self.assertFalse(self.b.discoverCastDevices())
        generation=self.b._cast_generation
        self.b._apply_cast_devices(generation,[dict(id='audio',name='Speaker',kind='audio')],False,'')
        self.assertEqual(len(self.b.castState['devices']),2)
        self.assertTrue(self.b.discoverCastDevices());self.scanner.refresh.assert_called_once()
        self.factory.assert_called_once();self.b.shutdown();self.scanner.close.assert_called_once()
        self.assertFalse(self.b.discoverCastDevices())

    def test_inventory_during_playback_is_offline_and_does_not_change_queue_audio_position_or_status(self):
        self.start('A','B');self.b._player_position=42;self.b._set_connected(False)
        queue=self.b._queue;current=queue.current();played=list(self.played);stops=list(self.stops)
        self.b._ytmusic=Mock();status=self.b.status
        self.b.discoverCastDevices()
        self.b._apply_cast_devices(self.b._cast_generation,[dict(id='group',name='Group',kind='group')],False,'')
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current)
        self.assertEqual(self.b.playerState,'playing');self.assertEqual(self.b.playerPosition,42)
        self.assertEqual(self.played,played);self.assertEqual(self.stops,stops);self.assertEqual(self.b.status,status)
        self.assertFalse(self.b._ytmusic.mock_calls)

    def test_error_can_restart_and_stale_result_cannot_replace_new_inventory(self):
        self.b.discoverCastDevices();old=self.b._cast_generation
        self.b._apply_cast_devices(old,[],False,'Discovery failed')
        self.assertFalse(self.b.castState['scanning']);self.assertTrue(self.b.discoverCastDevices())
        self.assertEqual(self.factory.call_count,2)
        self.b._apply_cast_devices(old,[dict(id='stale',name='Stale',kind='audio')],False,'')
        self.assertEqual(len(self.b.castState['devices']),1);self.assertTrue(self.b.castState['scanning'])
        self.b._apply_cast_devices(self.b._cast_generation,[],False,'')
        self.assertIn('nebyly nalezeny',self.b.castState['message'])

    def test_thread_start_failure_is_retryable_and_keeps_local_output(self):
        self.scanner.start.side_effect=RuntimeError('thread limit')
        self.assertTrue(self.b.discoverCastDevices());self.assertFalse(self.b.castState['scanning'])
        self.assertEqual(self.b.castState['devices'][0]['id'],'local')
        self.assertIsNone(self.b._cast_discovery)
