import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


@pytest.fixture(scope="session")
def cliente():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def clasificar(cliente):
    def _f(texto, **extra):
        return cliente.post("/v1/clasificar", json={"texto": texto, **extra})
    return _f
