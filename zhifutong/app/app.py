from contextlib import asynccontextmanager

from fastapi import FastAPI

from zhifutong.app.chat_router import chat_router
from zhifutong.app.dependencies import init_dialogue_engine
from zhifutong.clients.database_client import init_database, close_database
from zhifutong.clients.http_client import init_http_client, close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_http_client()
    init_database()
    init_dialogue_engine()
    yield
    await close_database()
    await close_http_client()


app = FastAPI(lifespan=lifespan)

app.include_router(chat_router)
