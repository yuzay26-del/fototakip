"""Arayüz bütünlüğü: app.js'te kullanılan her CSS sınıfının styles.css'te bir kuralı olmalı.

Kuralsız sınıf telefonda düzeni bozar (ör. .set-row yokken anahtar düğmesi 'Kaydet'in üstüne biniyordu).
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Yalnızca JS'in seçici olarak kullandığı, görünümü olmayan sınıflar
JS_ONLY = {"integ", "map-chip"}


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class ArayuzTest(unittest.TestCase):
    def test_every_class_has_css(self):
        js = read("web", "app.js")
        css = read("web", "styles.css") + read("web", "vendor", "leaflet", "leaflet.css")
        used = {c for m in re.finditer(r'class="([^"$]*)"', js) for c in m.group(1).split()}
        defined = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))
        self.assertEqual(sorted(used - defined - JS_ONLY), [])


if __name__ == "__main__":
    unittest.main()
