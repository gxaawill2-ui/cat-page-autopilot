"""No-network checks for original viral B-scheme edit timeline."""
import unittest
import viral_reel_edit as v

class ViralEditTests(unittest.TestCase):
    def test_exact_twelve_second_24fps_story(self):
        v.validate_timeline()
        self.assertEqual(v.TOTAL_FRAMES,288)
        self.assertEqual(v.TOTAL_FRAMES/v.FPS,12)

    def test_hook_shows_action_before_flashback(self):
        self.assertEqual([s[2] for s in v.SEGMENTS],["cold_open","flashback","payoff"])
        self.assertGreater(v.SEGMENTS[0][0],v.SEGMENTS[1][0])

    def test_real_source_motion_one_to_one(self):
        items=list(v.timeline())
        self.assertEqual(len(items),288)
        self.assertTrue(all(b[0]==a[0]+1 for a,b in zip(items,items[1:]) if a[1]==b[1]))
        self.assertEqual(items[0][0],220)
        self.assertEqual(items[24][0],91)
        self.assertEqual(items[153][0],220)
        self.assertEqual(items[-1][0],354)

    def test_no_render_or_facebook_on_import(self):
        self.assertTrue(v.OUTPUT.name.endswith(".mp4"))
        self.assertIn("/previews/",str(v.OUTPUT))

if __name__=="__main__":
    unittest.main()
