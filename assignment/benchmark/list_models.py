
import os
from pathlib import Path

import truststore
from dotenv import load_dotenv
from gigachat import GigaChat

truststore.inject_into_ssl()

ROOT_DIR = Path(__file__).resolve().parents[2]
CERT_PATH = Path(__file__).resolve().parent / "certs" / "russian_trusted_root_ca_pem.crt"

load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("GIGACHAT_AUTH_KEY")

if not api_key:
    raise RuntimeError("Ключ GIGACHAT_AUTH_KEY не найден")

with GigaChat(
    credentials=api_key,
    scope="GIGACHAT_API_PERS",
    ca_bundle_file=str(CERT_PATH),
) as client:

    models = client.get_models()

    print("Доступные модели GigaChat:")

    for model in models.data:
        print("-", model.id_)
