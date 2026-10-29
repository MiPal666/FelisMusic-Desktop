"""Artist channel subscriptions are separate from saved songs and playback."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support
from felismusic_gui.diagnostics import Trace


class ArtistSubscriptionTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.api=Mock();self.b._ytmusic=self.api;self.b._set_connected(True)
        self.b._library_section='artists';self.subscribed=False;self.channel='UCsubscribe';self.missing=False
        self.ignore_write=False
        self.b._artist_subscription_verify_delays=(0.0,0.0,0.0)
        self.api.get_artist.side_effect=self.artist
        self.api.subscribe_artist.side_effect=lambda cid:self.write(cid,True)
        self.api.unsubscribe_artists.side_effect=lambda ids:self.write(ids[0],False)
        self.api.get_library_artists.return_value=[dict(artist='Saved artist',browseId='MPLAUCbrowse')]
        self.rows=[dict(videoId=vid,title=vid,duration='3:00',likeStatus='LIKE') for vid in ('X','Y','X')]
        rows=self.rows
        class Pages:
            def __init__(self,*args):pass
            def next_page(self):return deepcopy(rows[:1]),False
        pager=patch.object(support.backend,'LibraryArtistSongPages',Pages);pager.start();self.addCleanup(pager.stop)

    def artist(self,bid):
        result=dict(name='Artist',channelId=self.channel,subscribed=self.subscribed,
                    songs=dict(results=deepcopy(self.rows)))
        if self.missing:result.pop('subscribed')
        return result

    def write(self,cid,value):
        self.assertEqual(cid,'UCsubscribe')
        if not self.ignore_write:self.subscribed=value
        return {}

    def open(self,bid='UCbrowse'):
        self.b.openLibraryItem('artist',bid,'','Artist');self.until(lambda:not self.b.busy)

    def change(self):
        self.assertTrue(self.b.changeArtistSubscription());self.until(lambda:not self.b.busy)

    def test_subscribe_unsubscribe_uses_returned_channel_and_keeps_audio_song_ratings_and_cover(self):
        self.open();self.b.playFrom('detail',2);self.until(lambda:self.b.playerState=='playing')
        before=deepcopy(self.b.detailTracksModel.snapshot());queue=self.b._queue;current=queue.current()
        self.b._player_position=42;played=list(self.played);stops=list(self.stops)
        self.change();self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')
        self.b.clearDetail();self.assertTrue(self.b.restorePlayingSource(1))
        self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])
        self.change();self.api.unsubscribe_artists.assert_called_once_with(['UCsubscribe'])
        self.assertFalse(self.b.detailMeta['artistSubscription']['subscribed'])
        self.assertEqual(self.b.detailTracksModel.snapshot(),before)
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current)
        self.assertEqual(self.b.playerPosition,42);self.assertEqual(self.played,played);self.assertEqual(self.stops,stops)
        self.assertEqual(self.b.playerLikeStatus,'LIKE');self.api.rate_song.assert_not_called()
        self.api.edit_song_library_status.assert_not_called()
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['browseId'],'MPLAUCbrowse')

    def test_library_artist_preserves_scope_and_normalizes_only_browse_alias_not_channel_id(self):
        self.open('MPLAUCbrowse');scope=self.b.detailMeta['songScope'];rows=self.b.detailTracksModel.snapshot()
        self.change()
        self.assertEqual(self.b.detailMeta['songScope'],scope);self.assertEqual(self.b.detailTracksModel.snapshot(),rows)
        self.api.get_artist.assert_any_call('UCbrowse')
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')

    def test_missing_state_changed_channel_and_upload_or_profile_never_write(self):
        self.missing=True;self.open();self.assertFalse(self.b.changeArtistSubscription())
        self.missing=False;self.open();self.channel='UCother';self.change()
        self.assertFalse(self.b.detailCanArtistSubscription);self.assertTrue(self.errors)
        self.api.subscribe_artist.assert_not_called()
        self.channel='UCsubscribe';self.open()
        for kind in ('upload_artist','channel','album','playlist'):
            self.b._detail_meta['kind']=kind
            self.assertFalse(self.b.changeArtistSubscription())
        self.api.subscribe_artist.assert_not_called()

    def test_external_subscription_change_is_idempotent(self):
        self.open();self.subscribed=True;self.change()
        self.api.subscribe_artist.assert_not_called();self.api.unsubscribe_artists.assert_not_called()
        self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])

    def test_delayed_readback_for_subscribe_and_unsubscribe_retries_only_reads(self):
        self.open()
        for wanted in (True,False):
            with self.subTest(wanted=wanted):
                before=self.artist('UCbrowse')
                after=dict(before,subscribed=wanted)
                self.api.get_artist.side_effect=[before,before,before,after]
                start=self.api.get_artist.call_count
                self.change()
                self.assertEqual(self.api.get_artist.call_count-start,4)
                self.assertEqual(self.b.detailMeta['artistSubscription']['subscribed'],wanted)
                self.assertTrue(self.b.detailCanArtistSubscription)
                self.assertFalse(self.errors)
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')
        self.api.unsubscribe_artists.assert_called_once_with(['UCsubscribe'])

    def test_transient_read_error_and_missing_state_can_recover_without_another_write(self):
        self.open();before=self.artist('UCbrowse');after=dict(before,subscribed=True)
        self.api.get_artist.side_effect=[before,ValueError('temporary parser error'),{},after]
        self.change()
        self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])
        self.assertFalse(self.errors)
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')

    def test_real_trace_stale_beyond_third_read_can_confirm_both_directions(self):
        self.open()
        # Use the production schedule, replacing only the clock wait.
        delays=support.backend.BackendBridge._artist_subscription_verify_delays
        self.b._artist_subscription_verify_delays=delays
        self.assertEqual(len(delays),6);self.assertEqual(sum(delays),15)
        for wanted in (True,False):
            with self.subTest(wanted=wanted):
                before=self.artist('UCbrowse');after=dict(before,subscribed=wanted)
                self.api.get_artist.side_effect=[before]*6+[after]
                with patch.object(self.b._closing,'wait',return_value=False) as wait:
                    self.change()
                self.assertEqual([c.args[0] for c in wait.call_args_list],list(delays))
                self.assertEqual(self.b.detailMeta['artistSubscription']['subscribed'],wanted)
                self.assertFalse(self.errors)
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')
        self.api.unsubscribe_artists.assert_called_once_with(['UCsubscribe'])

    def test_confirmation_stops_before_remaining_long_backoff(self):
        self.open()
        self.b._artist_subscription_verify_delays=support.backend.BackendBridge._artist_subscription_verify_delays
        before=self.artist('UCbrowse');after=dict(before,subscribed=True)
        self.api.get_artist.side_effect=[before,before,before,after]
        with patch.object(self.b._closing,'wait',return_value=False) as wait:
            self.change()
        self.assertEqual([c.args[0] for c in wait.call_args_list],[0.0,0.5,1.5])
        self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')

    def test_wrong_readback_channel_stops_verification_and_never_claims_success(self):
        self.open();before=self.artist('UCbrowse')
        self.api.get_artist.side_effect=[before,dict(before,channelId='UCother',subscribed=True)]
        self.change()
        self.assertFalse(self.b.detailCanArtistSubscription);self.assertTrue(self.errors)
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')

    def test_shutdown_interrupts_verification_before_another_read(self):
        self.b._closing.set()
        try:
            with self.assertRaises(RuntimeError):
                self.b._verify_artist_subscription(self.api,'UCbrowse','UCsubscribe',True)
            self.api.get_artist.assert_not_called()
        finally:
            self.b._closing.clear()

    def test_debug_distinguishes_rejected_response_from_stale_readback_without_account_data(self):
        self.open();output=io.StringIO();trace=Trace('api.artist_subscription_action')
        self.api.subscribe_artist.side_effect=None
        self.api.subscribe_artist.return_value={'status':'PRIVATESTATUS','secret':'PRIVATEBODY'}
        with redirect_stdout(output), patch.object(support.backend,'current_trace',return_value=trace):
            self.change()
        events=[json.loads(line.split('] ',1)[1]) for line in output.getvalue().splitlines()
                if line.startswith('[FelisMusic diag] ')]
        self.assertTrue(any(e['event']=='subscription.write_end' and e['status']=='other' for e in events))
        self.assertFalse(any(e['event']=='subscription.readback' for e in events))
        self.assertNotIn('PRIVATE',output.getvalue());self.assertNotIn('UCsubscribe',output.getvalue())
        self.assertNotIn('UCbrowse',output.getvalue())
        self.open();output=io.StringIO();self.api.subscribe_artist.return_value={}
        with redirect_stdout(output), patch.object(support.backend,'current_trace',return_value=trace):
            self.change()
        events=[json.loads(line.split('] ',1)[1]) for line in output.getvalue().splitlines()
                if line.startswith('[FelisMusic diag] ')]
        reads=[e for e in events if e['event']=='subscription.readback']
        self.assertEqual(len(reads),3)
        self.assertTrue(all(e['wanted'] and e['channel_matches'] and not e['subscribed'] for e in reads))
        self.assertEqual(self.api.subscribe_artist.call_count,2)

    def test_write_failure_and_unverified_result_invalidate_state_without_repeat(self):
        for fail in (True,False):
            self.open();self.ignore_write=not fail
            self.api.subscribe_artist.side_effect=RuntimeError('offline') if fail else lambda cid:self.write(cid,True)
            before=self.api.subscribe_artist.call_count
            self.change();self.assertFalse(self.b.detailCanArtistSubscription)
            self.assertFalse(self.b.changeArtistSubscription());self.assertEqual(self.api.subscribe_artist.call_count,before+1)
            self.assertTrue(self.errors)

    def test_pending_write_keeps_target_while_navigation_moves_and_blocks_repeats(self):
        self.open();entered=Event()
        def write(cid):entered.set();self.release.wait(3);return self.write(cid,True)
        self.api.subscribe_artist.side_effect=write
        self.assertTrue(self.b.changeArtistSubscription());self.until(entered.is_set)
        self.assertFalse(self.b.changeArtistSubscription())
        self.b._detail_meta=dict(kind='artist',browseId='UCother')
        self.release.set();self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailMeta,dict(kind='artist',browseId='UCother'))
        self.api.subscribe_artist.assert_called_once_with('UCsubscribe')

    def test_overview_failure_keeps_verified_state_and_offline_closing_guard(self):
        self.open();self.api.get_library_artists.side_effect=RuntimeError('overview offline')
        self.change();self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])
        self.assertIn('Přehled Interpretů',self.b.status)
        self.b._set_connected(False);self.assertFalse(self.b.changeArtistSubscription())
        self.b._set_connected(True);self.b._closing.set()
        self.assertFalse(self.b.changeArtistSubscription());self.b._closing.clear()

    def test_confirmed_state_updates_other_browse_variant_of_same_subscription_channel(self):
        self.open();state=self.b._detail_state();state['meta']['browseId']='UCvariant'
        self.b._detail_history=[state]
        self.change()
        self.assertTrue(self.b._detail_history[0]['meta']['artistSubscription']['subscribed'])
