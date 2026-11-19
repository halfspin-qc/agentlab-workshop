"""Run a cloud red-teaming scan against an agent with the Foundry AI Red Teaming Agent.

Example
  python 04_red_team.py --agent claims-coverage-agent:2
Results: Foundry portal > Build > Evaluations (red teaming runs show attack success rate by risk and strategy).
"""
import argparse
import time

from azure.ai.projects.models import AgentTaxonomyInput, AzureAIAgentTarget, EvaluationTaxonomy, RiskCategory

from common import clients, env, parse_agent

p = argparse.ArgumentParser()
p.add_argument("--agent", default=None, help="name or name:version (default: latest AGENT_NAME)")
p.add_argument("--strategies", default="Flip,Base64,IndirectJailbreak")
p.add_argument("--turns", type=int, default=3)
args = p.parse_args()

name, version = parse_agent(args.agent or env("AGENT_NAME"))
judge = env("JUDGE_MODEL")
project, client = clients()
if not version:
    version = project.agents.get(name).versions.latest.version
print(f"Red teaming {name}:{version}")

red_team = client.evals.create(
    name=f"red-team-{name}",
    data_source_config={"type": "azure_ai_source", "scenario": "red_team"},
    testing_criteria=[
        {"type": "azure_ai_evaluator", "name": "Prohibited Actions",
         "evaluator_name": "builtin.prohibited_actions", "evaluator_version": "1"},
        {"type": "azure_ai_evaluator", "name": "Task Adherence", "evaluator_name": "builtin.task_adherence",
         "evaluator_version": "1", "initialization_parameters": {"deployment_name": judge}},
        {"type": "azure_ai_evaluator", "name": "Sensitive Data Leakage",
         "evaluator_name": "builtin.sensitive_data_leakage", "evaluator_version": "1"},
    ],
)

target = AzureAIAgentTarget(name=name, version=version)
taxonomy = project.beta.evaluation_taxonomies.create(
    name=f"{name}-{version}",
    taxonomy=EvaluationTaxonomy(
        description="VanCan claims agent: prohibited actions such as confirming payouts or skipping escalation",
        taxonomy_input=AgentTaxonomyInput(risk_categories=[RiskCategory.PROHIBITED_ACTIONS], target=target),
    ),
)

run = client.evals.runs.create(
    eval_id=red_team.id, name=f"red-team-{name}-{version}",
    data_source={
        "type": "azure_ai_red_team",
        "item_generation_params": {
            "type": "red_team_taxonomy",
            "attack_strategies": [s.strip() for s in args.strategies.split(",")],
            "num_turns": args.turns,
            "source": {"type": "file_id", "id": taxonomy.id},
        },
        "target": target.as_dict(),
    },
)
print(f"Started red team run {run.id}. This usually takes 10 to 30 minutes.")
while True:
    run = client.evals.runs.retrieve(run_id=run.id, eval_id=red_team.id)
    print(f"  status: {run.status}")
    if run.status in ("completed", "failed", "canceled"):
        break
    time.sleep(30)

counts = getattr(run, "result_counts", None)
if counts:
    print(f"Attacks: {counts.total} | defended (passed): {counts.passed} | succeeded (failed): {counts.failed} | errors: {counts.errored}")
    if counts.total:
        print(f"Attack success rate: {counts.failed / counts.total:.0%}")
print("Open Build > Evaluations in the Foundry portal for the per-risk breakdown.")
