"""
Proactive behavior worker — runs as a separate process.

    cd backend && python -m worker.scheduler

Each tick:
  1. Fetches all agents
  2. Runs each through the decision function
  3. Executes an action if warranted (diary, log, status update, inter-agent visit)

The decision function is NOT purely time-based: it weighs time of day,
hours since last action, and whether other agents have been active recently.
"""
import sys
import os
import time
import logging

# Allow imports from backend/ root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db.supabase import db
from app.services.proactive_service import maybe_act
from app.config import SCHEDULER_INTERVAL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def tick() -> None:
    agents = db.table("living_agents").select("*").execute().data or []
    log.info("[Scheduler] tick — %d agents", len(agents))

    for agent in agents:
        try:
            maybe_act(agent)
        except Exception as e:
            log.error("[Scheduler] error processing %s: %s", agent.get("name"), e)


def run() -> None:
    log.info("[Scheduler] worker started, interval=%ds", SCHEDULER_INTERVAL)
    while True:
        tick()
        time.sleep(SCHEDULER_INTERVAL)


if __name__ == "__main__":
    run()
