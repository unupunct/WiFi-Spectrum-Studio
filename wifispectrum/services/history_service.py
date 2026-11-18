"""SQLite persistence for scan history and recommendations."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

from ..core.models import ScanSnapshot
from ..core.platform import data_dir

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    adapter TEXT,
    adapter_name TEXT,
    backend TEXT,
    demo INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    duration_ms REAL,
    band TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    bssid TEXT NOT NULL,
    ssid TEXT,
    channel INTEGER,
    frequency_mhz INTEGER,
    width_mhz INTEGER,
    rssi INTEGER,
    security TEXT,
    vendor TEXT,
    phy TEXT,
    band TEXT,
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_obs_scan ON observations(scan_id);
CREATE INDEX IF NOT EXISTS idx_obs_bssid ON observations(bssid, ts);
CREATE INDEX IF NOT EXISTS idx_obs_ts ON observations(ts);
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER,
    ts REAL,
    band TEXT,
    channel INTEGER,
    reason TEXT,
    confidence TEXT,
    score REAL,
    networks INTEGER
);
CREATE INDEX IF NOT EXISTS idx_rec_ts ON recommendations(ts);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started REAL,
    ended REAL,
    mode TEXT,
    adapter TEXT,
    networks INTEGER
);
"""


class HistoryError(RuntimeError):
    pass


class HistoryService:
    def __init__(self, path: str | Path | None = None, retention_days: int = 30):
        self._path = Path(path) if path else (data_dir() / "history.db")
        self._lock = threading.RLock()
        self._retention_days = retention_days
        self._last_observation_ts = 0.0
        self._observation_interval = 6.0
        self._conn: sqlite3.Connection | None = None
        self._open()

    # -- lifecycle ---------------------------------------------------------
    def _open(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False, timeout=8)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        except sqlite3.Error as exc:
            self._conn = None
            raise HistoryError(f"Could not open the history database: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def available(self) -> bool:
        return self._conn is not None

    # -- writes ------------------------------------------------------------
    def record(self, snapshot: ScanSnapshot, band: str | None = None, recommendation: dict | None = None) -> int | None:
        if not self._conn:
            return None
        now = time.time()
        store_obs = (now - self._last_observation_ts) >= self._observation_interval
        adapter = snapshot.adapter
        try:
            with self._lock:
                cur = self._conn.execute(
                    "INSERT INTO scans (ts, adapter, adapter_name, backend, demo, total, duration_ms, band, error) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        snapshot.timestamp,
                        adapter.interface if adapter else "",
                        adapter.name if adapter else "",
                        snapshot.backend,
                        1 if snapshot.demo else 0,
                        snapshot.total,
                        snapshot.duration_ms,
                        band or "",
                        snapshot.error,
                    ),
                )
                scan_id = int(cur.lastrowid)
                if store_obs and snapshot.aps:
                    self._conn.executemany(
                        "INSERT INTO observations (scan_id, ts, bssid, ssid, channel, frequency_mhz, width_mhz, "
                        "rssi, security, vendor, phy, band) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [
                            (
                                scan_id,
                                snapshot.timestamp,
                                ap.bssid,
                                ap.ssid,
                                ap.channel,
                                ap.frequency_mhz,
                                ap.width_mhz,
                                ap.rssi,
                                ap.security,
                                ap.vendor,
                                ap.phy,
                                ap.band.key,
                            )
                            for ap in snapshot.aps
                        ],
                    )
                    self._last_observation_ts = now
                if recommendation:
                    self._conn.execute(
                        "INSERT INTO recommendations (scan_id, ts, band, channel, reason, confidence, score, networks) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (
                            scan_id,
                            snapshot.timestamp,
                            str(recommendation.get("band", "")),
                            int(recommendation.get("channel", 0)),
                            str(recommendation.get("reason", "")),
                            str(recommendation.get("confidence", "")),
                            float(recommendation.get("score", 0.0)),
                            int(recommendation.get("networks", 0)),
                        ),
                    )
                self._conn.commit()
                return scan_id
        except sqlite3.Error as exc:
            log.error("History write failed: %s", exc)
            return None

    def prune(self, retention_days: int | None = None) -> int:
        days = retention_days if retention_days is not None else self._retention_days
        if not self._conn or days <= 0:
            return 0
        cutoff = time.time() - days * 86400
        try:
            with self._lock:
                cur = self._conn.execute("DELETE FROM observations WHERE ts < ?", (cutoff,))
                removed = cur.rowcount
                self._conn.execute("DELETE FROM scans WHERE ts < ?", (cutoff,))
                self._conn.execute("DELETE FROM recommendations WHERE ts < ?", (cutoff,))
                self._conn.commit()
            return max(0, removed)
        except sqlite3.Error as exc:
            log.warning("History prune failed: %s", exc)
            return 0

    def clear(self) -> None:
        if not self._conn:
            return
        with self._lock:
            for table in ("observations", "recommendations", "scans", "sessions"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    # -- reads -------------------------------------------------------------
    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        if not self._conn:
            return []
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def recent_scans(self, limit: int = 60) -> list[dict]:
        rows = self._rows(
            "SELECT id, ts, adapter, adapter_name, backend, demo, total, duration_ms, band FROM scans "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]

    def scan_networks(self, scan_id: int) -> list[dict]:
        rows = self._rows(
            "SELECT bssid, ssid, channel, frequency_mhz, width_mhz, rssi, security, vendor, phy, band "
            "FROM observations WHERE scan_id = ? ORDER BY rssi DESC",
            (scan_id,),
        )
        return [dict(row) for row in rows]

    def scan_count(self) -> int:
        rows = self._rows("SELECT COUNT(*) AS c FROM scans")
        return int(rows[0]["c"]) if rows else 0

    def observation_count(self) -> int:
        rows = self._rows("SELECT COUNT(*) AS c FROM observations")
        return int(rows[0]["c"]) if rows else 0

    def first_last(self) -> tuple[float | None, float | None]:
        rows = self._rows("SELECT MIN(ts) AS first, MAX(ts) AS last FROM scans")
        if not rows:
            return None, None
        return rows[0]["first"], rows[0]["last"]

    def db_size(self) -> int:
        try:
            return self._path.stat().st_size
        except OSError:
            return 0

    def band_summary(self, hours: int = 24) -> dict[str, dict]:
        cutoff = time.time() - hours * 3600
        rows = self._rows(
            "SELECT band, COUNT(DISTINCT bssid) AS networks, AVG(rssi) AS avg_rssi, MAX(ts) AS last_ts "
            "FROM observations WHERE ts >= ? GROUP BY band",
            (cutoff,),
        )
        return {row["band"]: dict(row) for row in rows}

    def network_series(self, bssid: str, hours: int = 24, limit: int = 600) -> list[tuple[float, int]]:
        cutoff = time.time() - hours * 3600
        rows = self._rows(
            "SELECT ts, rssi FROM observations WHERE bssid = ? AND ts >= ? ORDER BY ts ASC LIMIT ?",
            (bssid, cutoff, limit),
        )
        return [(row["ts"], row["rssi"]) for row in rows]

    def channel_history(self, band: str, hours: int = 24) -> dict[int, int]:
        cutoff = time.time() - hours * 3600
        rows = self._rows(
            "SELECT channel, COUNT(*) AS c FROM observations WHERE band = ? AND ts >= ? GROUP BY channel",
            (band, cutoff),
        )
        return {int(row["channel"]): int(row["c"]) for row in rows}

    def recommendations(self, limit: int = 20) -> list[dict]:
        rows = self._rows(
            "SELECT ts, band, channel, reason, confidence, score, networks FROM recommendations "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]

    def compare_scans(self, scan_a: int, scan_b: int) -> dict:
        a = {row["bssid"]: row for row in self.scan_networks(scan_a)}
        b = {row["bssid"]: row for row in self.scan_networks(scan_b)}
        added = [bssid for bssid in b if bssid not in a]
        removed = [bssid for bssid in a if bssid not in b]
        rssi_delta = {
            bssid: int(b[bssid]["rssi"]) - int(a[bssid]["rssi"])
            for bssid in a.keys() & b.keys()
        }
        return {"added": added, "removed": removed, "rssi_delta": rssi_delta}

    def all_scans_for_export(self, limit: int = 500) -> list[dict]:
        scans = self.recent_scans(limit)
        for scan in scans:
            scan["networks"] = self.scan_networks(scan["id"])
        return scans
