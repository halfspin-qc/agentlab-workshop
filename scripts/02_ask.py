"""Ask the agent one question, or replay a file of questions and report latency and tokens.

Examples
  python 02_ask.py --agent claims-coverage-agent "Assess claim CLM-2026-0101."
  python 02_ask.py --agent claims-coverage-agent:2 --file ../evals/sample-traffic.txt
Every call is traced in Foundry once Application Insights is connected (Agents > Traces).
"""
import argparse
import statistics
import time

import openai

from common import agent_reference, clients, env

p = argparse.ArgumentParser()
p.add_argument("question", nargs="?", help="a single question")
p.add_argument("--agent", default=None, help="name or name:version (default: AGENT_NAME, latest version)")
p.add_argument("--file", help="text file with one question per line")
p.add_argument("--quiet", action="store_true", help="with --file, print only the summary")
args = p.parse_args()

ref = args.agent or env("AGENT_NAME")
_, openai_client = clients()
questions = [q.strip() for q in open(args.file, encoding="utf-8") if q.strip()] if args.file else [args.question]
if not questions or questions == [None]:
    p.error("give a question or --file")

latencies, tokens, blocked = [], [], 0
for q in questions:
    start = time.perf_counter()
    try:
        response = openai_client.responses.create(input=q, extra_body=agent_reference(ref))
    except openai.BadRequestError as err:
        # Usually a guardrail block (jailbreak, indirect attack, PII). Count it and carry on.
        blocked += 1
        if not args.quiet or len(questions) == 1:
            print(f"\n>>> {q}\n[blocked or rejected: {getattr(err, 'message', err)}]")
        continue
    elapsed = time.perf_counter() - start
    latencies.append(elapsed)
    usage = getattr(response, "usage", None)
    if usage is not None:
        tokens.append(usage.total_tokens)
    if not args.quiet:
        print(f"\n>>> {q}\n{response.output_text}\n[{elapsed:.1f}s, {usage.total_tokens if usage else '?'} tokens, response {response.id}]")

if len(questions) > 1 and latencies:
    p95 = sorted(latencies)[max(0, int(round(0.95 * len(latencies))) - 1)]
    print(f"\n{ref}: {len(questions)} questions | latency p50 {statistics.median(latencies):.1f}s, p95 {p95:.1f}s"
          + (f" | avg tokens {statistics.mean(tokens):.0f}" if tokens else "")
          + (f" | blocked {blocked}" if blocked else ""))
