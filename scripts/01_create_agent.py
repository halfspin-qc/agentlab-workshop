"""Create a new version of the claims coverage agent from the instructions in /agent.

Examples
  python 01_create_agent.py --instructions v1                     # the prototype
  python 01_create_agent.py --instructions v2                     # production instructions
  python 01_create_agent.py --instructions v2 --model model-router
  python 01_create_agent.py --instructions v2 --name claims-coverage-agent-ci   # used by the pipeline

Prints the new agent reference as name:version on the last line.
"""
import argparse
import os

from azure.ai.projects.models import FileSearchTool, PromptAgentDefinition, RaiConfig

from common import AGENT_DIR, clients, env, get_or_create_vector_store

FILES = {"v1": "instructions-v1-prototype.md", "v2": "instructions-v2-production.md"}

p = argparse.ArgumentParser()
p.add_argument("--instructions", default="v2", help="v1, v2, or a path to a markdown file")
p.add_argument("--model", default=None, help="model deployment name (default: AGENT_MODEL)")
p.add_argument("--name", default=None, help="agent name (default: AGENT_NAME)")
p.add_argument("--guardrail", default=None, help="guardrail name to attach (default: GUARDRAIL_NAME, optional)")
p.add_argument("--rebuild-knowledge", action="store_true", help="re-upload the knowledge files")
args = p.parse_args()

name = args.name or env("AGENT_NAME")
model = args.model or env("AGENT_MODEL")
guardrail = args.guardrail if args.guardrail is not None else env("GUARDRAIL_NAME", required=False)
path = AGENT_DIR / FILES[args.instructions] if args.instructions in FILES else args.instructions
instructions = open(path, encoding="utf-8").read()

project, openai_client = clients()
vs = get_or_create_vector_store(openai_client, rebuild=args.rebuild_knowledge)

extra = {}
if guardrail:
    # Guardrails are created in the portal (Build > Guardrails). If the service rejects this
    # name, assign the guardrail in the portal instead: agent playground > Guardrails > Manage.
    extra["rai_config"] = RaiConfig(rai_policy_name=guardrail)

definition = PromptAgentDefinition(
    model=model,
    instructions=instructions,
    tools=[FileSearchTool(vector_store_ids=[vs.id], max_num_results=8)],
    **extra,
)

agent = project.agents.create_version(
    agent_name=name,
    definition=definition,
    description=f"VanCan claims coverage agent ({os.path.basename(str(path))}, {model})",
    metadata={"instructions": os.path.basename(str(path)), "model": model, "source": "workshop-scripts"},
)
print(f"Created {agent.name} version {agent.version} on {model}" + (f" with guardrail {guardrail}" if guardrail else ""))
print(f"{agent.name}:{agent.version}")
