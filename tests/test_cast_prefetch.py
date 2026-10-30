"""Prepare one Cast URL, without downloading audio or controlling next media."""
from collections import Counter
from threading import Event
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from test_cast_output import CastOutputFixture
from felismusic_gui.cast_streams import CastStreamCache


class CastPrefetchTests(CastOutputFixture):
    def setUp(self):
        super().setUp()
        self.requests=Counter();self.url_blocked=set();self.url_fail_once=set()
        self.stream_call.side_effect=self.resolve
        self.switch()

    def resolve(self, video_id, mc):
        self.requests[video_id]+=1;number=self.requests[video_id]
        if video_id in self.url_blocked:self.release.wait(3)
        if video_id in self.url_fail_once:
            self.url_fail_once.remove(video_id);raise RuntimeError('PRIVATE_SIGNED_URL')
        return f'https://audio.invalid/{video_id}?request={number}','audio/mp4'

    def prepared(self, video_id):
        self.until(lambda:self.requests[video_id]>0 and self.b._prefetch_future is not None
                   and self.b._prefetch_future.done())

    def finish_song(self):
        self.remote_status.player_state='IDLE';self.remote_status.idle_reason='FINISHED'
        self.b._poll_player()

    def test_one_url_is_ready_before_eos_with_no_audio_download_or_early_load(self):
        self.start('A','B','C');self.prepared('B')
        self.assertEqual(self.requests,Counter(A=1,B=1));self.assertFalse(self.downloads)
        self.assertEqual(self.remote.play_media.call_count,1);self.assertEqual(self.b._queue.index,0)
        self.finish_song();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.prepared('C');self.assertEqual(self.requests['B'],1)
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/B?request=1')
        self.assertFalse(self.downloads);self.assertFalse(self.errors)

    def test_eos_reuses_inflight_url_and_never_runs_two_extractions(self):
        self.url_blocked.add('B');self.start('A','B');self.until(lambda:self.requests['B']==1)
        self.finish_song();self.assertEqual(self.b.playerState,'loading')
        self.release.set();self.until(lambda:self.b.playerState=='playing' and self.b.playerTitle=='B')
        self.assertEqual(self.requests['B'],1);self.assertEqual(self.remote.play_media.call_count,2)

    def test_speculative_failure_is_silent_and_foreground_retries_same_song(self):
        self.url_fail_once.add('B');self.start('A','B');self.prepared('B')
        self.assertEqual(self.b.playerTitle,'A');self.assertFalse(self.errors)
        self.finish_song();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.assertEqual(self.requests['B'],2);self.assertFalse(self.errors)

    def test_rejected_prepared_load_uses_fresh_url_before_skipping_occurrence(self):
        self.start('A','B','C');self.prepared('B');original=self.remote.play_media.side_effect
        def load(url,*args,**kwargs):
            if url=='https://audio.invalid/B?request=1':kwargs['callback_function'](False,{})
            else:original(url,*args,**kwargs)
        self.remote.play_media.side_effect=load
        self.finish_song();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.assertEqual(self.b._queue.index,1);self.assertEqual(self.requests['B'],2)
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/B?request=2')
        self.assertFalse(self.errors)

    def test_expired_url_uses_fresh_resolution(self):
        self.start('A','B');self.prepared('B')
        with patch('felismusic_gui.cast_streams.monotonic',return_value=10**15):
            self.finish_song();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.assertEqual(self.requests['B'],2)

    def test_move_during_extraction_discards_old_successor_and_prepares_new_one(self):
        self.url_blocked.add('B');self.start('A','B','C');self.until(lambda:self.requests['B']==1)
        self.assertTrue(self.b.moveQueueItem(2,-1));self.release.set();self.prepared('C')
        self.finish_song();self.until(lambda:self.b.playerTitle=='C' and self.b.playerState=='playing')
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/C?request=1')
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks],['A','C','B'])

    def test_new_queue_during_extraction_never_plays_old_url(self):
        self.url_blocked.add('B');self.start('A','B');self.until(lambda:self.requests['B']==1)
        self.b._library_items_model.set_items([dict(kind='song',videoId='D',title='D')])
        self.b.playFrom('library',0);self.release.set()
        self.until(lambda:self.b.playerTitle=='D' and self.b.playerState=='playing')
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/D?request=1')
        self.assertEqual(self.remote.play_media.call_count,2)

    def test_removing_prepared_successor_uses_new_next_song(self):
        self.start('A','B','C');self.prepared('B')
        self.assertTrue(self.b.removeQueueItem(1));self.prepared('C')
        self.finish_song();self.until(lambda:self.b.playerTitle=='C' and self.b.playerState=='playing')
        self.assertEqual(self.requests['C'],1)
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/C?request=1')

    def test_appending_after_last_song_prepares_new_successor(self):
        self.start('A')
        self.b._library_items_model.set_items([dict(kind='song',videoId='B',title='B')])
        self.assertTrue(self.b.enqueueFrom('library',0,False,{'page':1}));self.prepared('B')
        self.assertEqual(self.remote.play_media.call_count,1)
        self.finish_song();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.assertEqual(self.requests['B'],1)

    def test_stop_invalidates_inflight_url_before_manual_restart(self):
        self.url_blocked.add('B');self.start('A','B');self.until(lambda:self.requests['B']==1)
        self.b.stopPlayback();self.release.set();self.b._playback_executor.submit(lambda:None).result(timeout=4)
        self.b.togglePlayPause();self.until(lambda:self.b.playerState=='playing');self.prepared('B')
        self.finish_song();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/B?request=2')

    def test_repeat_one_prepares_current_song_for_replay_without_moving_queue(self):
        self.start('A','B');self.prepared('B');self.b.cycleRepeat();self.b.cycleRepeat();self.prepared('A')
        self.finish_song();self.until(lambda:not self.b._playback_transitioning)
        self.assertEqual(self.b._queue.index,0);self.assertEqual(self.b.playerRepeatMode,'one')
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/A?request=2')

    def test_repeat_all_prepares_first_song_at_end_and_keeps_duplicates(self):
        self.start('A','A');self.prepared('A');self.b.cycleRepeat()
        self.finish_song();self.until(lambda:self.b._queue.index==1 and self.b.playerState=='playing')
        self.until(lambda:self.b._prefetch_future.done())
        self.finish_song();self.until(lambda:self.b._queue.index==0 and self.b.playerState=='playing')
        self.assertEqual(len(self.b._queue.tracks),2)
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/A?request=3')

    def test_loss_during_preparation_never_loads_or_retains_late_url(self):
        self.url_blocked.add('B');self.start('A','B');self.until(lambda:self.requests['B']==1)
        output=self.b._cast_output;output.new_connection_status(SimpleNamespace(status='LOST'))
        self.b._poll_player();self.release.set();self.b._playback_executor.submit(lambda:None).result(timeout=4)
        self.assertEqual(self.remote.play_media.call_count,1);self.assertTrue(self.b.castState['disconnected'])
        self.assertIsNone(self.b._cast_streams.take((self.b._queue,output,'B')))

    def test_return_to_local_discards_pending_cast_url_and_keeps_local_cache(self):
        self.url_blocked.add('B');self.start('A','B');self.until(lambda:self.requests['B']==1)
        output=self.b._cast_output;queue=self.b._queue
        self.assertTrue(self.b.selectLocalOutput());self.release.set()
        self.until(lambda:not self.b._output_switching)
        self.assertEqual(self.b.outputName,'Toto zařízení');self.assertEqual(self.b.playerState,'playing')
        self.until(lambda:'B' in self.downloads)
        self.assertIsNone(self.b._cast_streams.take((queue,output,'B')));self.assertFalse(self.errors)

    def test_shutdown_discards_late_preparation_without_loading_next_song(self):
        self.url_blocked.add('B');self.start('A','B');self.until(lambda:self.requests['B']==1)
        queue,output=self.b._queue,self.b._cast_output
        self.b.shutdown();self.release.set();self.until(lambda:self.b._prefetch_future.done())
        self.assertIsNone(self.b._cast_streams.take((queue,output,'B')))
        self.assertEqual(self.remote.play_media.call_count,1)


class CastStreamCacheTests(TestCase):
    def test_ttl_and_advertised_expiry_are_conservative(self):
        cache=CastStreamCache();key=(object(),object(),'A')
        with patch('felismusic_gui.cast_streams.time',return_value=1000), patch('felismusic_gui.cast_streams.monotonic',return_value=10):
            self.assertTrue(cache.complete(cache.reserve(key),('https://audio.invalid/?expire=1100','audio/mp4')))
        with patch('felismusic_gui.cast_streams.monotonic',return_value=81):self.assertIsNone(cache.take(key))
        with patch('felismusic_gui.cast_streams.monotonic',return_value=10):
            self.assertTrue(cache.complete(cache.reserve(key),('https://audio.invalid/A','audio/mp4')))
        with patch('felismusic_gui.cast_streams.monotonic',return_value=611):self.assertIsNone(cache.take(key))

    def test_invalid_expiry_is_not_cached(self):
        for expiry in ('0','garbage','nan','inf'):
            cache=CastStreamCache();key=(object(),object(),'A')
            self.assertFalse(cache.complete(cache.reserve(key),(f'https://audio.invalid/?expire={expiry}','audio/mp4')))
            self.assertIsNone(cache.take(key))

    def test_single_entry_is_scoped_to_queue_and_connection_and_consumed_once(self):
        cache=CastStreamCache();queue,output=object(),object();key=(queue,output,'A')
        source=('https://PRIVATE_SIGNED_URL/A','audio/mp4')
        cache.complete(cache.reserve(key),source)
        self.assertIsNone(cache.take((queue,object(),'A')))
        cache.complete(cache.reserve(key),source)
        self.assertIsNone(cache.take((object(),output,'A')))
        cache.complete(cache.reserve(key),source)
        self.assertEqual(cache.take(key),source);self.assertIsNone(cache.take(key))

    def test_reservation_deduplicates_and_old_completion_cannot_replace_new_successor(self):
        cache=CastStreamCache();key=(object(),object(),'A');old=cache.reserve(key)
        self.assertIsNone(cache.reserve(key));other=(key[0],key[1],'B');new=cache.reserve(other)
        self.assertFalse(cache.complete(old,('https://audio.invalid/A','audio/mp4')))
        self.assertTrue(cache.complete(new,('https://audio.invalid/B','audio/mp4')))
        self.assertIsNone(cache.reserve(other));self.assertEqual(cache.take(other)[0],'https://audio.invalid/B')

    def test_clear_blocks_late_completion(self):
        cache=CastStreamCache();key=(object(),object(),'A');ticket=cache.reserve(key);cache.clear()
        self.assertFalse(cache.complete(ticket,('https://audio.invalid/A','audio/mp4')))
        self.assertIsNone(cache.take(key))
