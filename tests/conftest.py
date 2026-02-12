from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.config import settings
from app.database import engine
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    settings.enable_background_jobs = False
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
