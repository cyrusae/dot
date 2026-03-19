"""
APScheduler-based scheduler for Dot.

Reads job definitions from scheduler.yaml, supports interval/cron/date triggers,
enqueues AgentEvent objects to an asyncio.Queue, and hot-reloads when scheduler.yaml changes.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .models import AgentEvent


@dataclass
class SchedulerJob:
    name: str
    trigger: str          # "interval" | "cron" | "date"
    tick_type: str        # "admin_message" | "operational_check" | "deep_reflection"
    prompt: str = ""      # event text (empty for perch-time ticks)
    harness: Optional[str] = None  # None = use default
    # For interval trigger:
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    # For cron trigger:
    cron: str = ""        # standard cron expression e.g. "0 9 * * *"
    # For date trigger:
    run_date: str = ""    # ISO format


class DotScheduler:
    def __init__(self, scheduler_yaml: Path, event_queue: asyncio.Queue):
        self.scheduler_yaml = scheduler_yaml
        self.event_queue = event_queue
        self._scheduler = AsyncIOScheduler()
        self._last_mtime: float = 0.0

    def start(self):
        self._load_jobs()
        # Check for scheduler.yaml changes every 30 seconds
        self._scheduler.add_job(
            self._check_reload,
            IntervalTrigger(seconds=30),
            id="_hot_reload_check",
        )
        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    async def _check_reload(self):
        if not self.scheduler_yaml.exists():
            return
        mtime = self.scheduler_yaml.stat().st_mtime
        if mtime != self._last_mtime:
            self._load_jobs()

    def _load_jobs(self):
        """Load/reload job definitions from scheduler.yaml."""
        if not self.scheduler_yaml.exists():
            return

        try:
            data = yaml.safe_load(self.scheduler_yaml.read_text())
            self._last_mtime = self.scheduler_yaml.stat().st_mtime
        except Exception as e:
            print(f"[scheduler] Failed to load scheduler.yaml: {e}")
            return

        # Remove all user-defined jobs (keep _hot_reload_check)
        for job in self._scheduler.get_jobs():
            if not job.id.startswith("_"):
                job.remove()

        jobs = data.get("jobs", []) if data else []
        for job_def in jobs:
            try:
                job = SchedulerJob(**job_def)
                self._add_job(job)
            except Exception as e:
                print(f"[scheduler] Failed to add job {job_def.get('name', '?')}: {e}")

        print(f"[scheduler] Loaded {len(jobs)} jobs from scheduler.yaml")

    def _add_job(self, job: SchedulerJob):
        if job.trigger == "interval":
            trigger = IntervalTrigger(
                hours=job.hours,
                minutes=job.minutes,
                seconds=job.seconds,
            )
        elif job.trigger == "cron":
            # Parse cron string "min hour day month dow"
            parts = job.cron.split()
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1],
                day=parts[2], month=parts[3], day_of_week=parts[4],
            )
        else:
            return  # date trigger deferred

        async def fire(j=job):
            event = AgentEvent(
                event_type="scheduler_tick",
                prompt=j.prompt,
                scheduler_name=j.name,
                tick_type=j.tick_type,
                harness=j.harness,
                source_platform="scheduler",
            )
            await self.event_queue.put(event)

        self._scheduler.add_job(fire, trigger, id=job.name, replace_existing=True)
