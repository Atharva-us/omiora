"""Entry point: `python -m omniora_api.worker`. Stops cleanly on SIGINT/SIGTERM."""

from __future__ import annotations

import signal
import threading

from ..config import get_settings
from ..db.session import make_engine, make_session_factory
from ..llm.factory import build_planning_provider
from ..logging_setup import configure_logging
from .discovery import DiscoveryJobHandler
from .planning import PlanningJobHandler
from .runner import Worker


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    factory = make_session_factory(make_engine(settings.database_url))
    provider = build_planning_provider(settings)
    worker = Worker(
        factory,
        PlanningJobHandler(factory, provider, settings),
        discovery=DiscoveryJobHandler(factory, provider, settings),
        lease_seconds=settings.worker_lease_seconds,
        poll_seconds=settings.worker_poll_seconds,
    )
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    worker.run_forever(stop)


if __name__ == "__main__":
    main()
