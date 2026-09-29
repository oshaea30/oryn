import threading
import unittest
from unittest.mock import Mock
from experience_feedback import ExperienceFeedback

class FeedbackQueueTests(unittest.TestCase):
    def test_late_lower_sequence_cannot_replace_cancellation(self):
        transport=Mock();entered=threading.Event();release=threading.Event();finished=threading.Event()
        def write(serial,notice):
            if notice['sequence']==11:entered.set();release.wait(3)
            if notice['sequence']==14:finished.set()
        transport.notice.side_effect=write
        feedback=ExperienceFeedback(transport)
        try:
            feedback.publish('device',{'session':'session','sequence':11})
            self.assertTrue(entered.wait(3))
            feedback.publish('device',{'session':'session','sequence':14})
            feedback.publish('device',{'session':'session','sequence':13})
            release.set();self.assertTrue(finished.wait(3))
            self.assertEqual([c.args[1]['sequence'] for c in transport.notice.call_args_list],[11,14])
        finally:release.set();feedback.close()

    def test_display_failure_does_not_kill_worker(self):
        transport=Mock();failed=threading.Event();done=threading.Event()
        def write(serial,notice):
            if notice['sequence']==11:failed.set();raise RuntimeError('USB unavailable')
            done.set()
        transport.notice.side_effect=write;feedback=ExperienceFeedback(transport)
        try:
            feedback.publish('device',{'session':'session','sequence':11});self.assertTrue(failed.wait(3))
            feedback.publish('device',{'session':'session','sequence':13});self.assertTrue(done.wait(3))
        finally:feedback.close()
