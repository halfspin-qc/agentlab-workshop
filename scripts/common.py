"""Shared helpers for the VanCan workshop scripts.

Auth: DefaultAzureCredential. Locally run `az login` first; in GitHub Actions the
azure/login step provides an Entra ID token through OIDC (no secrets).
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

ROOT = Path(__file__).resolve().parent.parent          # the workshop pack folder
KNOWLEDGE_DIR = ROOT / "data" / "knowledge"
AGENT_DIR = ROOT / "agent"
EVALS_DIR = ROOT / "evals"
VECTOR_STORE_NAME = "vancan-knowledge"

load_dotenv(Path(__file__).parent / ".env")


def env(name: str, default: str | None = None, required: bool = True) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing setting {name}. Add it to scripts/.env (see .env.sample).")
    return value or ""


def clients():
    """Return (project_client, openai_client) for the Foundry project."""
    project = AIProjectClient(endpoint=env("AZURE_AI_PROJECT_ENDPOINT"), credential=DefaultAzureCredential())
    return project, project.get_openai_client()


def parse_agent(ref: str) -> tuple[str, str | None]:
    """'name:3' -> ('name', '3'); 'name' -> ('name', None)."""
    name, _, version = ref.partition(":")
    return name, (version or None)


def agent_reference(ref: str) -> dict:
    name, version = parse_agent(ref)
    body = {"name": name, "type": "agent_reference"}
    if version:
        body["version"] = version
    return {"agent_reference": body}


def get_or_create_vector_store(openai_client, rebuild: bool = False):
    """Reuse the knowledge vector store if it exists, so every agent version shares the same knowledge."""
    if not rebuild:
        for vs in openai_client.vector_stores.list():
            if vs.name == VECTOR_STORE_NAME:
                print(f"Using vector store {vs.name} ({vs.id})")
                return vs
    vs = openai_client.vector_stores.create(name=VECTOR_STORE_NAME)
    for path in sorted(KNOWLEDGE_DIR.iterdir()):
        if path.is_file():
            with path.open("rb") as fh:
                openai_client.vector_stores.files.upload_and_poll(vector_store_id=vs.id, file=fh)
            print(f"  indexed {path.name}")
    print(f"Created vector store {vs.name} ({vs.id})")
    return vs
