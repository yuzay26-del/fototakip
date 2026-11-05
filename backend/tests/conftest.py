import os

# Testler yerel .env dosyasından etkilenmesin.
os.environ.setdefault("APP_MODE", "termux")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
