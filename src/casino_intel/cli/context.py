"""Shared CLI context: lazily-built clients/services, threaded through every
command via Typer's context object (contracts/cli-commands.md "Global contract").
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.drive.client import DriveClient
from casino_intel.models.ids import new_id
from casino_intel.sheets.change_log import ChangeLogWriter
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.config_loader import ConfigLoader, MetricRegistry
from casino_intel.sheets.writer import SheetsWriter
from casino_intel.validation.data_quality import DataQualityWriter


@dataclass
class AppContext:
    dry_run: bool = False
    ingestion_run_id: str = field(default_factory=lambda: new_id("ingestion_run"))
    actor: str = "cli"

    _spreadsheet_id: str | None = None
    _sheets_client: SheetsClient | None = None
    _drive_client: DriveClient | None = None
    _fingerprint_store: FingerprintStore | None = None
    _change_log: ChangeLogWriter | None = None
    _data_quality: DataQualityWriter | None = None
    _writer: SheetsWriter | None = None
    _config_loader: ConfigLoader | None = None
    _metric_registry: MetricRegistry | None = None

    @property
    def spreadsheet_id(self) -> str:
        if self._spreadsheet_id is None:
            self._spreadsheet_id = os.environ.get("SPREADSHEET_ID")
            if not self._spreadsheet_id:
                raise RuntimeError(
                    "SPREADSHEET_ID is not set — see .env.example. "
                    "Credentials/config are never accepted as CLI arguments."
                )
        return self._spreadsheet_id

    @property
    def sheets_client(self) -> SheetsClient:
        if self._sheets_client is None:
            self._sheets_client = SheetsClient(self.spreadsheet_id)
        return self._sheets_client

    @property
    def drive_client(self) -> DriveClient:
        if self._drive_client is None:
            self._drive_client = DriveClient()
        return self._drive_client

    @property
    def fingerprint_store(self) -> FingerprintStore:
        if self._fingerprint_store is None:
            store = FingerprintStore()
            # Warm a cold cache from the live workbook so idempotency (SC-005)
            # holds even on a fresh checkout / deleted local cache / first run
            # in a new environment — not just within one long-lived process
            # (services/cache_warmup.py). A brand-new, not-yet-initialised
            # workbook has nothing to warm from; that failure is expected and
            # an empty cache is the correct starting state in that case.
            from casino_intel.services.cache_warmup import warm_cache_from_sheets

            try:
                warm_cache_from_sheets(self.sheets_client, store)
            except Exception:
                pass
            self._fingerprint_store = store
        return self._fingerprint_store

    @property
    def change_log(self) -> ChangeLogWriter:
        if self._change_log is None:
            self._change_log = ChangeLogWriter(self.sheets_client, dry_run=self.dry_run)
        return self._change_log

    @property
    def data_quality(self) -> DataQualityWriter:
        if self._data_quality is None:
            self._data_quality = DataQualityWriter(self.sheets_client, dry_run=self.dry_run)
        return self._data_quality

    @property
    def writer(self) -> SheetsWriter:
        if self._writer is None:
            self._writer = SheetsWriter(
                self.sheets_client, self.fingerprint_store, self.change_log, dry_run=self.dry_run
            )
        return self._writer

    @property
    def config_loader(self) -> ConfigLoader:
        if self._config_loader is None:
            self._config_loader = ConfigLoader(self.sheets_client, dry_run=self.dry_run)
        return self._config_loader

    @property
    def metric_registry(self) -> MetricRegistry:
        if self._metric_registry is None:
            self._metric_registry = MetricRegistry("config/metrics.yaml")
        return self._metric_registry
