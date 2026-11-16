"""APK giriş noktası (android/app/src/main/python/fototakip_android.py): Termux olmadan başlatma ve durdurma."""

import os
import shutil
import sys
import tempfile
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "android", "app", "src", "main", "python"))

import fototakip_android as fa  # noqa: E402


class AndroidEntryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.files = os.path.join(self.tmp.name, "files")
        self.cache = os.path.join(self.tmp.name, "cache")
        os.makedirs(self.files)
        os.makedirs(self.cache)
        # Java tarafı web/ klasörünü APK'dan diske açar; burada kopyalayarak taklit ediyoruz.
        self.web = os.path.join(self.files, "web")
        shutil.copytree(os.path.join(ROOT, "web"), self.web)
        self._env = dict(os.environ)
        self._tempdir = tempfile.tempdir

    def tearDown(self):
        fa.stop()
        os.environ.clear()
        os.environ.update(self._env)
        tempfile.tempdir = self._tempdir
        self.tmp.cleanup()

    def start(self, cloudflared=""):
        fa.start(self.files, self.cache, self.web, cloudflared, 0)
        return f"http://127.0.0.1:{fa._server.server_address[1]}"

    def test_serves_ui_and_setup_code_from_android_dirs(self):
        base = self.start()
        self.assertTrue(fa.running())
        with urllib.request.urlopen(base + "/") as r:
            self.assertIn("FotoTakip", r.read().decode("utf-8"))
        code = fa.setup_code()
        self.assertRegex(code, r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertTrue(os.path.exists(os.path.join(self.files, "fototakip-data", "fototakip.db")))
        self.assertEqual(tempfile.gettempdir(), self.cache)

    def test_start_twice_is_harmless_and_stop_releases(self):
        self.start()
        first = fa._server
        fa.start(self.files, self.cache, self.web, "", 0)
        self.assertIs(fa._server, first)
        fa.stop()
        self.assertFalse(fa.running())
        self.assertEqual(fa.lan_urls(), [])

    def test_bundled_cloudflared_is_used_only_if_present(self):
        self.start(cloudflared=os.path.join(self.files, "yok", "libcloudflared.so"))
        self.assertNotIn("FOTOTAKIP_CLOUDFLARED", os.environ)
        fa.stop()
        binary = os.path.join(self.files, "libcloudflared.so")
        open(binary, "w").close()
        self.start(cloudflared=binary)
        self.assertEqual(os.environ["FOTOTAKIP_CLOUDFLARED"], binary)
        self.assertEqual(os.environ["GODEBUG"], "netdns=cgo")


if __name__ == "__main__":
    unittest.main()
