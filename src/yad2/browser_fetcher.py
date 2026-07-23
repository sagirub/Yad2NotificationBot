"""
CloakBrowser fetcher for Yad2.

Yad2's bot protection (Radware/ShieldSquare) blocks plain HTTP requests coming
from AWS IP ranges. A stealth browser (CloakBrowser — patched Chromium) defeats
the fingerprint-based challenge and returns the real listing pages even from an
AWS Lambda IP (verified: 17 items fetched from eu-west-2).

This module wraps CloakBrowser behind a small `fetch_html(url)` function.

IMPORTANT — asyncio + Playwright sync API:
    The scanner runs inside an asyncio event loop. Playwright's SYNC API cannot
    be called from within a running event loop ("It looks like you are using
    Playwright Sync API inside the asyncio loop."). To avoid this, ALL browser
    operations run inside a single dedicated background thread that owns the
    browser instance. `fetch_html` dispatches work to that thread and blocks for
    the result, so the sync Playwright calls never execute on the event loop.

Enable by setting the env var USE_CLOAKBROWSER=1.
"""

import concurrent.futures
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# Lambda only allows writes under /tmp. Point every cache/config path Chromium
# touches at /tmp so the browser is stable inside the container.
_TMP_DIRS = [
    "/tmp/.cache",
    "/tmp/.cache/fontconfig",
    "/tmp/.config",
    "/tmp/.local/share",
    "/tmp/.local/share/pki/nssdb",
    "/tmp/.run",
    "/tmp/.fontconfig",
]

# Chromium CLI args that keep it stable & headless inside Lambda.
# NOTE: intentionally NOT using --single-process (crashes on multi-page runs).
_CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--no-zygote",
    "--disable-crash-reporter",
    "--disable-breakpad",
]

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Single-thread executor: every browser call runs on this one thread, which
# keeps the sync Playwright API off the asyncio event loop.
_executor: concurrent.futures.ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()

# Browser state lives ON the executor thread (thread-local ownership).
_browser = None


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="cloakbrowser"
            )
        return _executor


def _ensure_tmp_dirs() -> None:
    for d in _TMP_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Could not create tmp dir {d}: {e}")


def _ensure_env() -> None:
    os.environ.setdefault("HOME", "/tmp")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/.cache")
    os.environ.setdefault("XDG_CONFIG_HOME", "/tmp/.config")
    os.environ.setdefault("XDG_DATA_HOME", "/tmp/.local/share")
    os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/.run")
    os.environ.setdefault("CLOAKBROWSER_SUPPRESS_FONT_WARNING", "1")


def _launch_browser_on_thread():
    """Runs ON the executor thread. Launches CloakBrowser."""
    from cloakbrowser import launch

    _ensure_tmp_dirs()
    _ensure_env()

    proxy = os.environ.get("CLOAK_PROXY")  # optional; not needed for AWS per tests
    launch_kwargs = {"headless": True, "args": list(_CHROMIUM_ARGS)}
    if proxy:
        launch_kwargs["proxy"] = proxy
        launch_kwargs["geoip"] = True
        logger.info("CloakBrowser launching WITH proxy")
    else:
        logger.info("CloakBrowser launching without proxy")

    return launch(**launch_kwargs)


def _get_browser_on_thread():
    """Runs ON the executor thread. Returns a live browser, launching if needed."""
    global _browser
    if _browser is None:
        _browser = _launch_browser_on_thread()
        logger.info("CloakBrowser launched (new instance)")
    return _browser


def _reset_browser_on_thread() -> None:
    """Runs ON the executor thread. Closes and discards the browser."""
    global _browser
    if _browser is not None:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
        logger.info("CloakBrowser instance reset")


def _fetch_on_thread(url: str, timeout_ms: int, settle_seconds: float) -> str:
    """Runs ON the executor thread. Performs the actual sync Playwright fetch."""
    last_err = None
    for attempt in range(2):  # one retry with a fresh browser if the first dies
        browser = _get_browser_on_thread()
        page = None
        try:
            page = browser.new_page(user_agent=_DEFAULT_UA)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(settle_seconds)  # native sleep (not CDP-visible)
            return page.content()
        except Exception as e:
            last_err = e
            logger.warning(
                f"CloakBrowser fetch failed (attempt {attempt + 1}/2) for {url}: {e}"
            )
            _reset_browser_on_thread()
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
    raise last_err if last_err else RuntimeError("CloakBrowser fetch failed")


def fetch_html(url: str, timeout_ms: int = 60000, settle_seconds: float = 3.0) -> str:
    """
    Fetch fully-rendered HTML for a URL using CloakBrowser.

    Safe to call from within an asyncio event loop: the browser work is executed
    on a dedicated single background thread and this call blocks for the result.

    Args:
        url: The URL to fetch.
        timeout_ms: Navigation timeout in milliseconds.
        settle_seconds: Extra wait after DOMContentLoaded for client-side render.

    Returns:
        The page HTML as a string.
    """
    future = _get_executor().submit(_fetch_on_thread, url, timeout_ms, settle_seconds)
    # Block for the result. Add headroom over the navigation timeout.
    return future.result(timeout=(timeout_ms / 1000) + settle_seconds + 30)


def reset_browser() -> None:
    """Close and discard the current browser (dispatched to the executor thread)."""
    try:
        _get_executor().submit(_reset_browser_on_thread).result(timeout=30)
    except Exception:
        pass


def is_enabled() -> bool:
    """True if CloakBrowser fetching is enabled via USE_CLOAKBROWSER env var."""
    return os.environ.get("USE_CLOAKBROWSER", "").lower() in ("1", "true", "yes")
