"""SCR-01 — atomic operator↔system file channel (Wave-0 stub).

Behavior (filled by 05-01 Task 2 — the atomic helper + boundary-safe channel):
  - atomic round-trip: write_json/read_json round-trips a dict exactly.
  - same-dir temp: the temp file lands in os.path.dirname(target), never another volume.
  - interleaved reader never sees a partial file across many rapid writes.
  - channel read_* on a malformed/half-present file returns a safe default, never raises.

Stubs are xfail(strict=False) so collection is green until 05-01 Task 2 flips them
to real assertions (this file is flipped in THIS plan, Task 2).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-01 Task 2 (opcomm.atomic)", strict=False)
def test_atomic_round_trip():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-01 Task 2 (same-dir temp)", strict=False)
def test_temp_is_same_dir():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-01 Task 2 (no partial read)", strict=False)
def test_interleaved_reader_never_partial():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-01 Task 2 (boundary read default)", strict=False)
def test_channel_read_malformed_returns_default():
    raise AssertionError("not implemented")
