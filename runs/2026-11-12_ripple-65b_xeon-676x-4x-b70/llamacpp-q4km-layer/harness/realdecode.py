#!/usr/bin/env python3
"""this run realistic decode probe: streamed chat on real tasks (code/prose), c=1 and c=4.
Reports per-stream decode tok/s = completion_tokens (incl. reasoning) / (t_last - t_first), plus
spec-decode acceptance delta from /metrics if present. Usage: realdecode.py [base] [model]"""
import json, os, sys, threading, time, urllib.request, re

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8200"
model = sys.argv[2] if len(sys.argv) > 2 else "ripple-65b-gptq-sd"
TASKS = [
    "Write a Python module implementing an LRU cache class with get/put, type hints, and pytest tests.",
    "Explain how TCP congestion control works (slow start, congestion avoidance, fast recovery) in about 400 words.",
    "Write a bash script that finds the 10 largest files under a directory, with argument parsing and error handling.",
    "Refactor this into idiomatic Rust and explain the changes: def f(xs):\n  out=[]\n  for x in xs:\n    if x%2==0: out.append(x*x)\n  return out",
]


def metrics():
    try:
        t = urllib.request.urlopen(base + "/metrics", timeout=10).read().decode()
    except Exception:
        return {}
    out = {}
    for k in ("num_drafts", "num_draft_tokens", "num_accepted_tokens"):
        m = re.search(rf"^vllm:spec_decode_{k}_total\{{[^}}]*\}} ([0-9.e+]+)", t, re.M)
        if m:
            out[k] = float(m.group(1))
    return out


def one(prompt, res):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500,
            "temperature": float(os.environ.get("RD_TEMP", "0.6")), "top_p": 0.95, "stream": True, "stream_options": {"include_usage": True}}
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.time(); first = last = None; n = 0
    with urllib.request.urlopen(req, timeout=900) as r:
        for line in r:
            if not line.startswith(b"data: ") or b"[DONE]" in line:
                continue
            d = json.loads(line[6:])
            if d.get("choices"):
                dl = d["choices"][0].get("delta", {})
                if dl.get("content") or dl.get("reasoning") or dl.get("reasoning_content"):
                    now = time.time(); first = first or now; last = now
            if d.get("usage"):
                n = d["usage"]["completion_tokens"]
    res.append((first - t0, n / (last - first) if last and last > first else 0.0, n))


for c in (1, 4):
    for trial in range(int(os.environ.get("RD_TRIALS", "2"))):
        m0 = metrics(); res = []
        prompts = [TASKS[(trial * 4 + i) % 4] for i in range(c)] if c > 1 else [TASKS[trial % 4]]
        ts = [threading.Thread(target=one, args=(p, res)) for p in prompts]
        w0 = time.time(); [t.start() for t in ts]; [t.join() for t in ts]; wall = time.time() - w0
        m1 = metrics()
        acc = ""
        if m0 and m1 and m1.get("num_drafts", 0) > m0.get("num_drafts", 0):
            dd = m1["num_drafts"] - m0["num_drafts"]; da = m1["num_accepted_tokens"] - m0["num_accepted_tokens"]
            dt = m1["num_draft_tokens"] - m0["num_draft_tokens"]
            acc = f" accept={da/dt:.1%} mean_accepted_len={1+da/dd:.2f}"
        print(f"c={c} trial={trial} TTFT={sum(r[0] for r in res)/c*1000:.0f}ms per-stream={sum(r[1] for r in res)/c:.1f} tok/s "
              f"aggregate={sum(r[2] for r in res)/wall:.1f} tok/s tokens={[r[2] for r in res]}{acc}", flush=True)
