import json
import tempfile
import unittest
from pathlib import Path
from stage_demo import SOURCE, stage_demo


class SelectedMovieTests(unittest.TestCase):
    def test_selected_bytes_and_provenance_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = stage_demo(Path(directory))
            for name in (*metadata['files'], 'recording.json'):
                self.assertEqual((SOURCE / name).read_bytes(), (Path(directory) / name).read_bytes())

    def test_changed_movie_rejected_before_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / 'source', Path(directory) / 'out'
            stage_demo(source)
            (source / 'monofuki.mp4').write_bytes(b'not the selected movie')
            with self.assertRaisesRegex(ValueError, 'Recording changed'):
                stage_demo(destination, source)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
