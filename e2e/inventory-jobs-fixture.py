"""Synthetic job histories, restricted to the disposable proxy-stack databases."""
from datetime import timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

from labadda import inventory_jobs as jobs
from labadda.config import load_settings
from labadda.db import session_factory
from labadda.models import InventoryJob
from labadda.security import utcnow

settings = load_settings()
url = make_url(settings.database_url)
assert settings.environment == 'test' and url.host == 'localhost'
assert url.database in {'labadda_e2e_root', 'labadda_e2e_prefix'}
factory = session_factory(settings.database_url)
settings.asset_dir.mkdir(parents=True, exist_ok=True)
for i in range(13):
    jobs.enqueue(factory, f'queued-browser-{i:02}', {})
completed = jobs.enqueue(factory, 'retried-browser-job', {})
missing = settings.asset_dir / 'synthetic-missing-inventory-root'
assert not missing.exists()
jobs.run(factory, missing, completed)
jobs.run(factory, settings.asset_dir, completed, retry=True)
expired = jobs.enqueue(factory, 'expired-browser-job', {})
jobs.claim(factory, expired)
with factory() as db:
    db.get(InventoryJob, expired).lease_until = utcnow() - timedelta(seconds=1)
    db.commit()
cancelled = jobs.enqueue(factory, 'cancelled-browser-job', {})
jobs.cancel(factory, cancelled)
print('Synthetic queued, retried, expired and cancelled inventory jobs prepared')
