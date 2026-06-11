"""Marks ``tests/`` as a real package so the project's tests win the ``tests`` import name.

Why this file exists: ``ultralytics`` (the heavy YOLO dep) ships its OWN top-level ``tests/``
package inside its wheel, which lands in site-packages with an ``__init__.py``. Without this
marker the repo's ``tests/`` is only a namespace dir, so `from tests.conftest import SEED/FPS`
resolves to ultralytics' ``tests`` (a regular package wins over a namespace) and every test
module errors at collection with `ImportError: cannot import name 'SEED'`. Making this directory
a regular package — found at the rootdir (sys.path[0] in pytest's prepend mode), ahead of
site-packages — guarantees `tests.*` always means OUR tests, in any env where ultralytics is
installed (the rig and any `.[heavy]` venv). Keep it empty.
"""
