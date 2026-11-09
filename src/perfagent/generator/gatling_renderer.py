"""Deterministic Gatling renderer: LoadModel -> a runnable Gatling simulation (Scala).

Gatling is popular for high-performance load testing. This produces a standard
Gatling simulation: one scenario per journey, HTTP requests per step, checks for
status/assertions, and an injection profile sized by weight. No LLM — pure templating.

Dynamic generators map to Gatling feeders/session functions where clean; otherwise a
Gatling EL expression `#{var}` is emitted for the user to wire up. k6 remains the
primary tool; this is for teams standardized on Gatling.
"""

from __future__ import annotations

import json
import re

from perfagent.contracts.load_model import LoadModel


def _ident(text: str, fallback: str) -> str:
    cleaned = re.sub(r"\W+", "_", text.strip()).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = "s_" + cleaned
    return cleaned


def _gen_to_gatling(value: str) -> str:
    """Map our ${...} tokens to Gatling expressions where possible."""
    def repl(m):
        tok = m.group(1)
        if tok == "uuid":
            return "${java.util.UUID.randomUUID()}"  # replaced below into EL-safe form
        # Gatling EL uses #{var}; for generators we inline session expressions instead.
        base = tok.split("(")[0]
        return "#{" + base + "}"
    # For simplicity and determinism, convert ${x} -> #{x} (Gatling EL).
    return re.sub(r"\$\{([^}]+)\}", repl, value)


def _request(step) -> str:
    name = step.name.replace('"', '\\"')
    method = step.method.value.lower()
    path = _gen_to_gatling(step.path)
    lines = [f'    exec(http("{name}")']
    lines.append(f'      .{method}("{path}")')
    if step.body:
        body = _gen_to_gatling(json.dumps(step.body)).replace('"', '\\"')
        lines.append('      .header("Content-Type", "application/json")')
        lines.append(f'      .body(StringBody("{body}"))')
    # checks
    checks = ['status.in(200 to 399)']
    for a in getattr(step, "assertions", []) or []:
        if a.kind == "status":
            checks.append(f"status.is({a.value})")
        elif a.kind == "body_contains":
            needle = a.value.replace('"', '\\"')
            checks.append(f'substring("{needle}").exists')
        elif a.kind == "json_path":
            jp = "$." + a.path.replace("[", "[").replace("]", "]")
            val = a.value.replace('"', '\\"')
            checks.append(f'jsonPath("{jp}").is("{val}")')
    lines.append("      .check(" + ", ".join(checks) + ")")
    lines.append("    )")
    # think time
    lo = step and 1
    return "\n".join(lines)


def render_gatling(model: LoadModel, filename: str = "LoadSimulation.scala") -> str:
    peak = model.load_profile.peak_users
    total = model.load_profile.total_seconds
    ramp = max(1, int(total * 0.2))
    fractions = model.normalised_weights()

    scenario_defs = []
    inject_lines = []
    for i, (sc, frac) in enumerate(zip(model.scenarios, fractions, strict=False)):
        var = _ident(sc.name, f"scenario{i}")
        think = sc.think_time
        body = []
        for st in sc.steps:
            body.append(_request(st))
            body.append(f"    .pause({think.min_seconds}, {think.max_seconds})")
        # chain the scenario: scenario("X").exec(...).pause(...)
        chained = []
        for b in body:
            b2 = b.lstrip()
            if b2.startswith("exec(") or b2.startswith(".pause"):
                chained.append("    ." + b2 if b2.startswith("exec(") else "    " + b2)
            else:
                chained.append("    " + b2)
        scn = (f'  val {var} = scenario("{sc.name}")\n' + "\n".join(chained))
        scenario_defs.append(scn)
        users = max(1, round(peak * frac))
        inject_lines.append(
            f"    {var}.inject(rampUsers({users}).during({ramp}.seconds))")

    scenarios = "\n\n".join(scenario_defs)
    injects = ",\n".join(inject_lines)

    return f'''import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

// Auto-generated Gatling simulation. Target: {model.target_base_url}
class LoadSimulation extends Simulation {{

  val httpProtocol = http
    .baseUrl("{model.target_base_url}")
    .acceptHeader("application/json")

{scenarios}

  setUp(
{injects}
  ).protocols(httpProtocol)
   .maxDuration({total}.seconds)
}}
'''
