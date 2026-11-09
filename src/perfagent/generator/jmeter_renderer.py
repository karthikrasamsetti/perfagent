"""Deterministic JMeter renderer: LoadModel -> a runnable .jmx test plan (XML).

JMeter is widely used in enterprise QA. This produces a standard JMeter Test Plan
with a Thread Group per scenario (sized by weight), an HTTP sampler per step, and a
Response Assertion for each step's status/assertions. No LLM — pure templating.

Note: dynamic generators (${uuid}, ${randomEmail}) and correlation are mapped to
JMeter's own functions/extractors where a clean equivalent exists; otherwise the
placeholder is left as a JMeter variable `${var}` for the user to wire up. k6 remains
the primary, fully-featured tool — this is for teams standardized on JMeter.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from perfagent.contracts.load_model import LoadModel


def _largest_remainder(peak: int, fractions: list[float]) -> list[int]:
    raw = [peak * f for f in fractions]
    floors = [int(x) for x in raw]
    rem = peak - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(rem):
        floors[order[i % len(order)]] += 1
    return [max(1, v) if fractions[i] > 0 else 0 for i, v in enumerate(floors)]


def _gen_to_jmeter(value: str) -> str:
    """Map our ${...} tokens to JMeter functions where possible."""
    import re
    def repl(m):
        tok = m.group(1)
        if tok == "uuid":
            return "${__UUID()}"
        if tok == "timestamp":
            return "${__time()}"
        if tok == "randomEmail":
            return "user_${__RandomString(8,abcdefghijklmnopqrstuvwxyz0123456789)}@loadtest.test"
        if tok.startswith("randomInt("):
            inner = tok[len("randomInt("):-1]
            lo, hi = [p.strip() for p in inner.split(",")]
            return f"${{__Random({lo},{hi})}}"
        if tok.startswith("randomString("):
            n = tok[len("randomString("):-1].strip()
            return f"${{__RandomString({n},abcdefghijklmnopqrstuvwxyz0123456789)}}"
        # fall back to a JMeter variable of the same name
        return "${" + tok.split("(")[0] + "}"
    return re.sub(r"\$\{([^}]+)\}", repl, value)


def _http_sampler(step, base_host: str, base_path: str, scheme: str) -> str:
    import json as _j
    method = step.method.value
    path = _gen_to_jmeter(step.path)
    body = ""
    post_bodyraw = "false"
    if step.body:
        post_bodyraw = "true"
        body = escape(_gen_to_jmeter(_j.dumps(step.body)))
    assertions = _response_assertions(step)
    return f'''        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{escape(step.name)}" enabled="true">
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments">
              {'<elementProp name="" elementType="HTTPArgument"><boolProp name="HTTPArgument.always_encode">false</boolProp><stringProp name="Argument.value">' + body + '</stringProp><stringProp name="Argument.metadata">=</stringProp></elementProp>' if body else ''}
            </collectionProp>
          </elementProp>
          <stringProp name="HTTPSampler.domain">{escape(base_host)}</stringProp>
          <stringProp name="HTTPSampler.protocol">{scheme}</stringProp>
          <stringProp name="HTTPSampler.path">{escape(base_path + path)}</stringProp>
          <stringProp name="HTTPSampler.method">{method}</stringProp>
          <boolProp name="HTTPSampler.postBodyRaw">{post_bodyraw}</boolProp>
        </HTTPSamplerProxy>
        <hashTree>
{assertions}        </hashTree>'''


def _response_assertions(step) -> str:
    parts = []
    # status assertion from any status assertion, else default 2xx-ish
    for a in getattr(step, "assertions", []) or []:
        if a.kind == "status":
            parts.append(f'''          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="status {escape(a.value)}" enabled="true">
            <collectionProp name="Asserion.test_strings"><stringProp name="0">{escape(a.value)}</stringProp></collectionProp>
            <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>
            <intProp name="Assertion.test_type">8</intProp>
          </ResponseAssertion>
          <hashTree/>''')
        elif a.kind in ("json_path", "body_contains"):
            needle = a.value if a.kind == "body_contains" else a.value
            parts.append(f'''          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="contains {escape(needle)}" enabled="true">
            <collectionProp name="Asserion.test_strings"><stringProp name="0">{escape(needle)}</stringProp></collectionProp>
            <stringProp name="Assertion.test_field">Assertion.response_data</stringProp>
            <intProp name="Assertion.test_type">16</intProp>
          </ResponseAssertion>
          <hashTree/>''')
    return ("\n".join(parts) + "\n") if parts else ""


def render_jmeter(model: LoadModel, filename: str = "loadtest.jmx") -> str:
    from urllib.parse import urlsplit
    sp = urlsplit(model.target_base_url)
    scheme = sp.scheme or "http"
    host = sp.hostname or "localhost"
    base_path = sp.path.rstrip("/")
    port = f'<stringProp name="HTTPSampler.port">{sp.port}</stringProp>' if sp.port else ""

    peak = model.load_profile.peak_users
    total = model.load_profile.total_seconds
    ramp = max(1, int(total * 0.2))
    fractions = model.normalised_weights()
    per_scenario = _largest_remainder(peak, fractions)

    thread_groups = []
    for sc, vus in zip(model.scenarios, per_scenario, strict=False):
        samplers = "\n".join(_http_sampler(st, host, base_path, scheme) for st in sc.steps)
        thread_groups.append(f'''      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="{escape(sc.name)}" enabled="true">
        <stringProp name="ThreadGroup.num_threads">{vus}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">{ramp}</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">{total}</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController">
          <boolProp name="LoopController.continue_forever">true</boolProp>
          <intProp name="LoopController.loops">-1</intProp>
        </elementProp>
      </ThreadGroup>
      <hashTree>
{samplers}
      </hashTree>''')

    groups_xml = "\n".join(thread_groups)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="{escape(model.target_base_url)} load test" enabled="true">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments"/>
    </TestPlan>
    <hashTree>
      {port}
{groups_xml}
    </hashTree>
  </hashTree>
</jmeterTestPlan>
'''
