from __future__ import annotations

import argparse
import json
import time

from redis import Redis

from driver_monitoring.backend.database import init_database, load_backend_config
from driver_monitoring.backend.jobs import get_queue, process_analysis_job


def main() -> None:
    parser = argparse.ArgumentParser(description="DriveGuard AI inference worker")
    parser.add_argument("--config", default="config.toml", help="Path to the config TOML file.")
    args = parser.parse_args()

    init_database(args.config)
    app_config = load_backend_config(args.config)

    if app_config.backend.queue_backend == "rq":
        from rq import Worker

        queue = get_queue(args.config)
        worker = Worker([queue], connection=queue.connection, name=f"{app_config.backend.queue_name}-worker")
        worker.work()
        return

    if app_config.backend.queue_backend == "redis":
        connection = Redis.from_url(app_config.backend.redis_url)
        queue_name = app_config.backend.queue_name
        while True:
            entry = connection.blpop(queue_name, timeout=5)
            if entry is None:
                time.sleep(0.2)
                continue
            _, raw_payload = entry
            payload = json.loads(raw_payload.decode("utf-8"))
            process_analysis_job(payload["job_id"], payload["config_path"])
        return

    raise RuntimeError("Worker requires backend.queue_backend to be 'redis' or 'rq'.")


if __name__ == "__main__":
    main()
