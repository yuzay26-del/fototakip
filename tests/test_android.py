"""APK giriş noktası (android/app/src/main/python/fototakip_android.py): Termux olmadan başlatma ve durdurma."""

import os
import shutil
import subprocess
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


class ApkLayoutTest(unittest.TestCase):
    """APK'daki düzen: Python paketinin yanında web/ yok; arayüz ayrı bir klasöre açılır."""

    def test_starts_without_web_next_to_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "pkg")
            shutil.copytree(os.path.join(ROOT, "fototakip"), os.path.join(pkg, "fototakip"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy(os.path.join(ROOT, "android", "app", "src", "main", "python", "fototakip_android.py"), pkg)
            files, cache = os.path.join(tmp, "files"), os.path.join(tmp, "cache")
            os.makedirs(cache)
            shutil.copytree(os.path.join(ROOT, "web"), os.path.join(files, "web"))
            script = (
                "import sys, urllib.request\n"
                f"sys.path.insert(0, {pkg!r})\n"
                "import fototakip_android as fa\n"
                f"fa.start({files!r}, {cache!r}, {os.path.join(files, 'web')!r}, '', 0)\n"
                "port = fa._server.server_address[1]\n"
                "body = urllib.request.urlopen(f'http://127.0.0.1:{port}/').read().decode()\n"
                "assert 'FotoTakip' in body, body[:200]\n"
                "import fototakip\n"
                f"assert fototakip.__file__.startswith({pkg!r}), fototakip.__file__\n"
                "fa.stop()\n"
                "print('ok')\n"
            )
            env = {k: v for k, v in os.environ.items() if k != "FOTOTAKIP_WEB"}
            r = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True,
                               timeout=60, cwd=tmp, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
