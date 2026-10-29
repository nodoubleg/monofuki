"""Verify the animation's grid contract and actual redraws, without waiting."""
import unittest
from unittest.mock import patch
from io import StringIO
import os

from terminal_demo import (ANIMATION_FPS, ANIMATION_SCENES, animate,
                           animation_frame, artwork, main, CELL_WIDTH, CELL_HEIGHT)


class AnimationTests(unittest.TestCase):
    def test_circle_physical_extent(self):
        points = []
        bits = ((1, 8), (2, 16), (4, 32), (64, 128))
        for row, line in enumerate(artwork(56, 14, circular=True)):
            for column, char in enumerate(line):
                for y in range(4):
                    for x in range(2):
                        if (ord(char) - 0x2800) & bits[y][x]:
                            points.append(((column * 2 + x + .5) * CELL_WIDTH / 2,
                                           (row * 4 + y + .5) * CELL_HEIGHT / 4))
        width = max(p[0] for p in points) - min(p[0] for p in points)
        height = max(p[1] for p in points) - min(p[1] for p in points)
        self.assertEqual(width, height)

    def test_small_terminal_rejected_before_escape_sequences(self):
        out = StringIO()
        with patch('sys.stdout', out), patch.object(out, 'isatty', return_value=True), \
             patch('sys.argv', ['demo', '--animate']), \
             patch('shutil.get_terminal_size', return_value=os.terminal_size((58, 23))), \
             patch('sys.stderr', StringIO()):
            with self.assertRaises(SystemExit):
                main()
        self.assertEqual(out.getvalue(), '')

    def test_frames_fit_viewport_and_move(self):
        for scene, seconds in ANIMATION_SCENES:
            frames = [animation_frame(scene, i / (seconds * ANIMATION_FPS - 1))
                      for i in range(seconds * ANIMATION_FPS)]
            self.assertGreater(len({tuple(f) for f in frames}), 30, scene)
            for frame in frames:
                self.assertLessEqual(len(frame), 22)
                self.assertLessEqual(max(map(len, frame)), 76)
                self.assertNotIn('\x1b', '\n'.join(frame))

    def test_status_meter_stays_enclosed(self):
        for phase in (0, .5, 1):
            lines = animation_frame('status', phase)
            self.assertEqual([len(line) for line in lines[7:10]], [54] * 3)
        self.assertIn('100%', '\n'.join(animation_frame('status', 1)))

    def test_redraw_clears_tails_and_restores_cursor(self):
        out = StringIO()
        with patch('terminal_demo.sys.stdout', out), patch('terminal_demo.time.sleep'):
            animate()
        text = out.getvalue()
        self.assertEqual(text.count('\x1b[H'), 22 * ANIMATION_FPS)
        self.assertEqual(text.count('\x1b[K'), 22 * 22 * ANIMATION_FPS)
        self.assertTrue(text.endswith('\x1b[0m\x1b[?25h\x1b[?1049l'))
        self.assertNotIn('\uf550', text)

    def test_interrupt_restores_cursor(self):
        out = StringIO()
        with patch('terminal_demo.sys.stdout', out), patch('terminal_demo.time.sleep', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                animate()
        self.assertTrue(out.getvalue().endswith('\x1b[0m\x1b[?25h\x1b[?1049l'))


if __name__ == '__main__':
    unittest.main()
