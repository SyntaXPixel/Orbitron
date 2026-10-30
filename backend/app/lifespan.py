import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.workers.operations_worker import worker

logger = logging.getLogger("orbitron.lifespan")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Orbitron backend starting up...")
    worker.start()
    yield
    # Shutdown
    logger.info("Orbitron backend shutting down...")
    await worker.stop()
