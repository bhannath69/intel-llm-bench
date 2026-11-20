#!/usr/bin/env python3
"""xetest.py — stdlib-only test harness for a running LLM server."""

import argparse
import datetime
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import statistics


BACKEND = "xestrata"
MODEL = "x"
CONTAINER = "xestrata-b70"


def effort_extra(effort):
    """Return backend-specific extra dict for reasoning/thinking control."""
    if BACKEND == "vllm":
        return {"chat_template_kwargs": {"enable_thinking": effort != "none"}}
    return {"reasoning_effort": effort}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def http_post(url, path, payload, timeout):
    """POST JSON to url+path. Returns (status_code, parsed_json_or_None)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{url}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        raise RuntimeError(f"POST {path}: {e}") from e


def http_get(url, path, timeout):
    """GET JSON from url+path. Returns (status_code, parsed_json_or_None)."""
    try:
        with urllib.request.urlopen(f"{url}{path}", timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        raise RuntimeError(f"GET {path}: {e}") from e


def get_last_timings(url, timeout):
    """Fetch /v1/status and return last_timings + machine blocks."""
    if BACKEND == "vllm":
        return {}, {}
    code, data = http_get(url, "/v1/status", timeout)
    if code != 200 or not data:
        return {}, {}
    return data.get("last_timings", {}), data.get("machine", {})


def count_tokens(url, messages, timeout):
    """Call token counting endpoint. Returns int."""
    if BACKEND == "vllm":
        code, data = http_post(url, "/tokenize",
                               {"model": MODEL, "messages": messages}, timeout)
        if code == 200 and data:
            return data["count"]
        raise RuntimeError(f"count_tokens returned {code}")
    code, data = http_post(url, "/v1/messages/count_tokens",
                           {"model": MODEL, "messages": messages}, timeout)
    if code == 200 and data:
        return data["input_tokens"]
    raise RuntimeError(f"count_tokens returned {code}")


def chat_completion(url, messages, max_tokens, stream=False, extra=None, timeout=1800):
    """Send a chat completion request. Returns dict of results."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if extra:
        payload.update(extra)

    if not stream:
        t0 = time.time()
        code, data = http_post(url, "/v1/chat/completions", payload, timeout)
        wall = time.time() - t0
        lt, mach = get_last_timings(url, timeout)
        if code != 200 or not data:
            return {"ok": False, "error": f"HTTP {code}", "wall_s": wall}
        choice = data["choices"][0]
        content = choice["message"].get("content", "")
        reasoning = choice["message"].get("reasoning_content") or ""
        finish = choice.get("finish_reason", "")
        usage = data.get("usage", {})
        return {
            "ok": True, "wall_s": wall, "content": content,
            "reasoning_content": reasoning, "finish_reason": finish,
            "usage": usage, "last_timings": lt, "machine": mach,
        }
    else:
        # Streaming
        buf = b""
        chunks = []
        t0 = time.time()
        ttft = None
        full_content = ""
        full_reasoning = ""
        usage = None

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{url}/v1/chat/completions", data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                while True:
                    # read1, NOT read: http.client's chunked read(amt) loops over SSE chunks until amt
                    # bytes have arrived (~15 tokens), so TTFT was measured late and short responses
                    # reported ttft == wall (2026-11-06, XQ1). read1 returns after the current chunk.
                    chunk = resp.read1(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.decode().strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            j = line[6:]
                            if j == "[DONE]":
                                break
                            try:
                                obj = json.loads(j)
                                chunks.append(obj)
                                delta = obj.get("choices", [{}])[0].get("delta", {})
                                dc = delta.get("content") or ""
                                dr = delta.get("reasoning_content") or ""
                                if ttft is None and (dc or dr):
                                    ttft = time.time() - t0
                                full_content += dc
                                full_reasoning += dr
                                if obj.get("usage"):
                                    usage = obj["usage"]
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            return {"ok": False, "error": str(e), "wall_s": time.time() - t0}

        wall = time.time() - t0
        lt, mach = get_last_timings(url, timeout)
        finish = ""
        for c in reversed(chunks):
            fr = c.get("choices", [{}])[0].get("finish_reason")
            if fr:
                finish = fr
                break
        return {
            "ok": True, "wall_s": wall, "ttft_s": ttft or wall,
            "content": full_content, "reasoning_content": full_reasoning,
            "finish_reason": finish, "usage": usage,
            "last_timings": lt, "machine": mach,
        }


# ── meta.json writer ─────────────────────────────────────────────────────────

def write_meta(out_dir, argv, url, timeout):
    docker_started = ""
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.StartedAt}}", CONTAINER],
            capture_output=True, text=True, timeout=10,
        )
        docker_started = r.stdout.strip()
    except Exception:
        pass
    if BACKEND == "vllm":
        _, v1_status = http_get(url, "/v1/models", timeout)
    else:
        _, v1_status = http_get(url, "/v1/status", timeout)
    meta = {
        "argv": argv,
        "start_time": datetime.datetime.now().astimezone().isoformat(),
        "docker_started_at": docker_started,
        "v1_status": v1_status,
        "backend": BACKEND,
        "model": MODEL,
        "container": CONTAINER,
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)


def ensure_out_dir(out_dir):
    """Create out_dir; refuse if it exists and is non-empty."""
    if os.path.exists(out_dir):
        entries = os.listdir(out_dir)
        if entries:
            print(f"RESULT DIR_REFUSE FAIL dir={out_dir} reason=non-empty", flush=True)
            sys.exit(2)
    else:
        os.makedirs(out_dir, exist_ok=True)


# ── CANARY ────────────────────────────────────────────────────────────────────

CANARY_PROMPT = (
    "Write a Python function that returns the n-th Fibonacci number iteratively, "
    "then explain its time complexity in two sentences."
)
INTERLEAVE_PROMPTS = ["Name three primary colours."]


def cmd_canary(args):
    print(f"backend={BACKEND} model={MODEL} container={CONTAINER}", flush=True)
    out_dir = args.out
    ensure_out_dir(out_dir)
    write_meta(out_dir, sys.argv, args.url, args.timeout)

    jln = os.path.join(out_dir, "canary.jsonl")
    hashes = []
    records = []

    for rep in range(args.n):
        # interleave throwaway
        if args.interleave:
            ir = chat_completion(
                args.url,
                [{"role": "user", "content": INTERLEAVE_PROMPTS[rep % len(INTERLEAVE_PROMPTS)]}],
                32, extra={**effort_extra(args.effort)}, timeout=args.timeout,
            )
            rec = {"kind": "interleave", "rep": rep, **ir}
            with open(jln, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")

        res = chat_completion(
            args.url,
            [{"role": "user", "content": CANARY_PROMPT}],
            args.max_tokens,
            # explicit greedy: from xe0.1.45 a request without sampling takes the MODEL CARD's (T 0.7), not greedy
            extra={**effort_extra(args.effort), "temperature": args.temperature},
            timeout=args.timeout,
        )
        combined = (res.get("reasoning_content", "") or "") + "\x00" + (res.get("content", "") or "")
        h = hashlib.sha256(combined.encode()).hexdigest()
        hashes.append(h)
        rec = {
            "kind": "canary", "rep": rep, "hash": h,
            "wall_s": res.get("wall_s"), "finish_reason": res.get("finish_reason"),
            "usage": res.get("usage"), "last_timings": res.get("last_timings"),
            "content": res.get("content", ""),
            "reasoning_content": res.get("reasoning_content", ""),
        }
        records.append(rec)
        with open(jln, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    unique = len(set(hashes))
    all_same = unique == 1
    first_diverge = -1
    if not all_same and len(records) > 1:
        base_text = (records[0].get("reasoning_content", "") or "") + "\x00" + (records[0].get("content", "") or "")
        for i in range(1, len(records)):
            other_text = (records[i].get("reasoning_content", "") or "") + "\x00" + (records[i].get("content", "") or "")
            for ci in range(min(len(base_text), len(other_text))):
                if base_text[ci] != other_text[ci]:
                    first_diverge = ci
                    # Write diff file
                    ctx = 100
                    start = max(0, first_diverge - ctx)
                    end_base = min(len(base_text), first_diverge + ctx)
                    end_other = min(len(other_text), first_diverge + ctx)
                    diff_path = os.path.join(out_dir, "canary-diff.txt")
                    with open(diff_path, "w") as df:
                        df.write(f"=== Divergence at character {first_diverge} ===\n\n")
                        df.write(f"--- rep 0 (chars {start}-{end_base}) ---\n")
                        df.write(base_text[start:end_base] + "\n\n")
                        df.write(f"+++ rep {i} (chars {start}-{end_other}) ---\n")
                        df.write(other_text[start:end_other] + "\n")
                    break

    verdict = "PASS" if all_same else "FAIL"
    result_line = f"RESULT CANARY {verdict} n={args.n} unique={unique} first_diverge_char={first_diverge}"
    print(result_line, flush=True)
    return 0 if all_same else 1


# ── NEEDLE ────────────────────────────────────────────────────────────────────

SUBJECTS = [
    "The committee", "The board", "The department", "The agency", "The division",
    "The council", "The panel", "The commission", "The team", "The group",
    "The directorate", "The task force", "The working group", "The subcommittee",
]
VERBS = [
    "reviewed", "examined", "assessed", "evaluated", "analyzed", "inspected",
    "audited", "surveyed", "investigated", "monitored", "tracked", "calculated",
]
OBJECTS = [
    "the quarterly logistics report", "the annual budget forecast",
    "the regional compliance audit", "the infrastructure upgrade plan",
    "the procurement tender", "the risk assessment matrix",
    "the operational efficiency study", "the market analysis brief",
    "the supply chain review", "the performance metrics dashboard",
]
LOCATIONS = [
    "for the northern warehouse", "at the eastern distribution center",
    "in the western office complex", "across the southern facility",
    "for the central hub", "at the primary depot", "in the secondary plant",
    "for the main campus", "at the satellite office", "in the regional branch",
]


def build_filler_paragraph(rng, section_idx):
    lines = []
    n_sentences = rng.randint(4, 8)
    for _ in range(n_sentences):
        subj = rng.choice(SUBJECTS)
        verb = rng.choice(VERBS)
        obj = rng.choice(OBJECTS)
        loc = rng.choice(LOCATIONS)
        day = rng.randint(1, 365)
        ref = rng.randint(100, 9999)
        lines.append(f"{subj} {verb} {obj} {loc} on day {day} (ref #{ref}).")
    return f"Section {section_idx}. " + " ".join(lines)


def build_needle_doc(num_paras, depth_frac, seed):
    """Build a needle-in-haystack document with exactly num_paras filler paragraphs.
    Returns (full_text, code)."""
    rng = random.Random(seed)
    # uuid4 (not seeded): no two documents may share a cached prompt prefix (2026-10-11 fix:
    # a seeded header made every size share its prefix and the engine reused up to 98K tokens).
    archive_uuid = uuid.uuid4().hex.upper()

    code_letters1 = "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
    code_digits = "".join(str(rng.randint(0, 9)) for _ in range(4))
    code_letters2 = "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
    code = f"{code_letters1}{code_digits}-{code_letters2}"

    paragraphs = []
    for i in range(num_paras):
        paragraphs.append(build_filler_paragraph(rng, i))

    needle_sentence = f"Important: the vault access code is {code}."
    insert_pos = int(num_paras * depth_frac)
    insert_pos = max(1, min(insert_pos, num_paras - 1))
    paragraphs.insert(insert_pos, needle_sentence)

    header = f"Archive batch {archive_uuid}"
    question = "Question: What is the vault access code mentioned in the archive above? Reply with the code only."
    full_text = header + "\n\n" + "\n\n".join(paragraphs) + "\n\n" + question
    return full_text, code


def size_to_target(url, target_size, depth_frac, seed, timeout):
    """Build document sized within +/-2% of target_size tokens.
    Calibrates tokens-per-paragraph, then uses at most 3 count_tokens calls
    to refine paragraph count. Returns (text, code, measured_tokens)."""
    # Step 1: calibrate tokens per paragraph using a deterministic sample
    cal_rng = random.Random(seed + 7777)
    sample_paras = [build_filler_paragraph(cal_rng, i) for i in range(20)]
    sample_text = "\n\n".join(sample_paras)
    sample_tokens = count_tokens(url, [{"role": "user", "content": sample_text}], timeout)
    tokens_per_para = sample_tokens / len(sample_paras)

    # Measure header + needle + question overhead
    overhead_rng = random.Random(seed)
    _uuid = str(uuid.UUID(int=overhead_rng.getrandbits(128))).upper()
    _code = "AB1234-CD"
    needle_line = f"Important: the vault access code is {_code}."
    header_q = f"Archive batch {_uuid}\n\n{needle_line}\n\nQuestion: What is the vault access code mentioned in the archive above? Reply with the code only."
    overhead_tokens = count_tokens(url, [{"role": "user", "content": header_q}], timeout)

    # Estimate paragraph count needed (body = target - overhead)
    body_tokens = target_size - overhead_tokens
    est_paras = max(10, round(body_tokens / tokens_per_para))

    best_text = None
    best_code = None
    best_tokens = None
    best_diff = float("inf")

    # Proportional rescale from each measurement (the calibration estimate ran ~9% short
    # at 128K+ on 2026-10-11; a bisection over a +/-4% span could never reach the target).
    mid = est_paras
    for _attempt in range(3):
        text, code = build_needle_doc(mid, depth_frac, seed)
        measured = count_tokens(url, [{"role": "user", "content": text}], timeout)
        diff_pct = abs(measured - target_size) / target_size * 100

        if diff_pct < best_diff:
            best_diff = diff_pct
            best_text = text
            best_code = code
            best_tokens = measured

        if diff_pct <= 2:
            break

        mid = max(10, round(mid * (target_size - overhead_tokens) / max(1, measured - overhead_tokens)))

    return best_text, best_code, best_tokens


def cmd_needle(args):
    print(f"backend={BACKEND} model={MODEL} container={CONTAINER}", flush=True)
    out_dir = args.out
    ensure_out_dir(out_dir)
    write_meta(out_dir, sys.argv, args.url, args.timeout)

    sizes = [int(s) for s in args.sizes.split(",")]
    jln = os.path.join(out_dir, "needle.jsonl")
    all_found = True
    found_count = 0

    for target in sizes:
        # per-size seed: a distinct code and distinct filler for every size
        text, code, measured = size_to_target(
            args.url, target, args.depth, args.seed * 1000003 + target, args.timeout,
        )

        res = chat_completion(
            args.url,
            [{"role": "user", "content": text}],
            args.max_tokens,
            stream=True,
            extra={**effort_extra(args.effort), "stream_options": {"include_usage": True}},
            timeout=args.timeout,
        )

        content = res.get("content", "")
        found = code.lower() in content.lower() if code else False
        if found:
            found_count += 1
        else:
            all_found = False

        prefill_tok_s = measured / (res.get("ttft_s", 1) or 1)

        # Wire decode speed
        n_ct = (res.get("usage") or {}).get("completion_tokens")
        n_ttft = res.get("ttft_s")
        n_wall = res.get("wall_s")
        if n_ct and n_ttft and n_wall and n_wall > n_ttft:
            n_decode_wire = n_ct / (n_wall - n_ttft)
        else:
            n_decode_wire = None
        n_cached = ((res.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")

        rec = {
            "target_tokens": target, "measured_input_tokens": measured,
            "code": code, "depth": args.depth,
            "ttft_s": res.get("ttft_s"), "total_s": res.get("wall_s"),
            "content": content,
            "reasoning_length": len(res.get("reasoning_content", "") or ""),
            "finish_reason": res.get("finish_reason"),
            "usage": res.get("usage"),
            "last_timings": res.get("last_timings"),
            "found": found, "prefill_tok_s": prefill_tok_s,
            "decode_wire_toks_s": n_decode_wire,
            "cached_tokens": n_cached,
        }
        with open(jln, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")

        print(f"  needle size={target} measured={measured} found={found} ttft={res.get('ttft_s', '?'):.3f}s", flush=True)

    verdict = "PASS" if all_found else "FAIL"
    result_line = f"RESULT NEEDLE {verdict} sizes={args.sizes} found={found_count}/{len(sizes)}"
    print(result_line, flush=True)
    return 0 if all_found else 1


# ── SOAK ──────────────────────────────────────────────────────────────────────

WORKLOAD_PROMPTS = [
    ("fix_bug", "Fix the bug and explain briefly:\n\ndef mean(xs):\n    return sum(xs) / len(xs) - 1\n"),
    ("parse_iso", "Write a Python function that parses ISO-8601 dates without external libraries, with three pytest tests."),
    ("invoice_extract", "Extract the fields as JSON (vendor, date, total, line_items[{desc, qty, unit_price}]): INVOICE #4471 from Northwind Supplies, dated 2026-03-14. 3 x Widget A @ 4.50; 1 x Gadget Pro @ 129.00; 12 x Bolt M6 @ 0.15. Total due 144.30."),
    ("incident_log", None),  # Built dynamically
    ("transistor_history", "Write a 300 word concise history of the transistor."),
]


def build_incident_log(seed):
    rng = random.Random(seed)
    svcs = ["auth-svc", "api-gw", "db-proxy", "cache-layer", "worker-pool", "scheduler", "metrics-collector"]
    levels = ["INFO", "WARN", "ERROR"]
    msgs_info = [
        "request processed successfully", "health check passed",
        "connection pool refreshed", "cache hit ratio nominal",
        "batch job completed", "config reloaded",
    ]
    msgs_warn = [
        "high latency detected on upstream", "connection pool near capacity",
        "retry attempt initiated", "slow query detected",
        "memory usage above threshold", "rate limit approaching",
    ]
    msgs_error = [
        "connection refused by downstream", "timeout exceeded",
        "circuit breaker tripped", "disk write failed",
        "authentication token expired", "deadlock detected",
    ]
    lines = []
    base_ts = datetime.datetime(2026, 10, 11, 3, 0, 0, tzinfo=datetime.timezone.utc)
    for i in range(200):
        ts = base_ts + datetime.timedelta(seconds=i * rng.randint(1, 10))
        svc = rng.choice(svcs)
        lvl = rng.choices(levels, weights=[60, 25, 15])[0]
        if lvl == "INFO":
            msg = rng.choice(msgs_info)
        elif lvl == "WARN":
            msg = rng.choice(msgs_warn)
        else:
            msg = rng.choice(msgs_error)
        lines.append(f"{ts.isoformat()} svc={svc} level={lvl} msg={msg}")
    log_text = "\n".join(lines)
    return log_text + "\n\nSummarise the incident above in 5 bullet points."


def get_docker_started():
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.StartedAt}}", CONTAINER],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def cmd_soak(args):
    print(f"backend={BACKEND} model={MODEL} container={CONTAINER}", flush=True)
    out_dir = args.out
    ensure_out_dir(out_dir)
    write_meta(out_dir, sys.argv, args.url, args.timeout)

    jln = os.path.join(out_dir, "soak.jsonl")
    machine_jln = os.path.join(out_dir, "machine.jsonl")

    # Build incident log once
    inc_log = build_incident_log(args.seed)
    WORKLOAD_PROMPTS[3] = ("incident_log", inc_log)

    docker_start = get_docker_started()
    start_time = time.time()
    end_time = start_time + args.duration

    idx = 0
    failed = 0
    canary_hashes = []
    canary_results = []
    stop_reason = "duration"
    workload_decode_speeds = []
    workload_wire_speeds = []
    draft_accepted_total = 0
    draft_n_total = 0
    per_prompt_walls = {}
    per_prompt_wire = {}
    all_wall_times = []
    all_wire_times = []

    last_machine_ts = start_time

    # Initial canary
    canary_res = chat_completion(
        args.url,
        [{"role": "user", "content": CANARY_PROMPT}],
        256, extra={**effort_extra("none"), "temperature": 0}, timeout=args.timeout,
    )
    canary_combined = (canary_res.get("reasoning_content", "") or "") + "\x00" + (canary_res.get("content", "") or "")
    canary_h = hashlib.sha256(canary_combined.encode()).hexdigest()
    canary_hashes.append(canary_h)
    canary_rec = {
        "idx": -1, "kind": "canary", "prompt_id": "canary",
        "t_start": datetime.datetime.now().astimezone().isoformat(),
        "wall_s": canary_res.get("wall_s"), "ok": canary_res.get("ok", False),
        "hash": canary_h, "content": canary_res.get("content", ""),
        "reasoning_content": canary_res.get("reasoning_content", ""),
        "finish_reason": canary_res.get("finish_reason"),
        "usage": canary_res.get("usage"), "last_timings": canary_res.get("last_timings"),
    }
    with open(jln, "a") as f:
        f.write(json.dumps(canary_rec, default=str) + "\n")

    next_canary_at = start_time + args.canary_every

    while True:
        now = time.time()

        # Check abort flag
        if os.path.exists("/tmp/sweep.abort"):
            stop_reason = "abort-flag"
            break

        # Check container restart
        current_start = get_docker_started()
        if current_start and current_start != docker_start:
            stop_reason = "container-restarted"
            break

        # Check duration
        if now >= end_time:
            stop_reason = "duration"
            break

        # Machine sampling every 60s
        if now - last_machine_ts >= 60:
            _, machine = get_last_timings(args.url, args.timeout)
            if machine:
                with open(machine_jln, "a") as f:
                    f.write(json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(), **machine}, default=str) + "\n")
            last_machine_ts = now

        # Canary check
        if now >= next_canary_at:
            c_res = chat_completion(
                args.url,
                [{"role": "user", "content": CANARY_PROMPT}],
                256, extra={**effort_extra("none"), "temperature": 0}, timeout=args.timeout,
            )
            c_combined = (c_res.get("reasoning_content", "") or "") + "\x00" + (c_res.get("content", "") or "")
            c_h = hashlib.sha256(c_combined.encode()).hexdigest()
            canary_hashes.append(c_h)
            c_rec = {
                "idx": idx, "kind": "canary", "prompt_id": "canary",
                "t_start": datetime.datetime.now().astimezone().isoformat(),
                "wall_s": c_res.get("wall_s"), "ok": c_res.get("ok", False),
                "hash": c_h, "content": c_res.get("content", ""),
                "reasoning_content": c_res.get("reasoning_content", ""),
                "finish_reason": c_res.get("finish_reason"),
                "usage": c_res.get("usage"), "last_timings": c_res.get("last_timings"),
            }
            with open(jln, "a") as f:
                f.write(json.dumps(c_rec, default=str) + "\n")
            next_canary_at += args.canary_every

        # Workload request
        prompt_id, prompt_text = WORKLOAD_PROMPTS[idx % len(WORKLOAD_PROMPTS)]
        seed_val = args.seed + idx

        res = chat_completion(
            args.url,
            [{"role": "user", "content": prompt_text}],
            1024,
            extra={
                **effort_extra(args.effort),
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20,
                "seed": seed_val,
                "stream_options": {"include_usage": True},
            },
            stream=True,
            timeout=args.timeout,
        )

        ok = res.get("ok", False)
        if not ok:
            failed += 1

        content_preview = (res.get("content", "") or "")[:200]
        lt = res.get("last_timings", {})
        if lt.get("predicted_per_second"):
            workload_decode_speeds.append(lt["predicted_per_second"])
        da = lt.get("draft_n_accepted", 0) or 0
        dn = lt.get("draft_n", 0) or 0
        draft_accepted_total += da
        draft_n_total += dn

        # Wire decode speed
        w_ttft = res.get("ttft_s")
        w_ct = (res.get("usage") or {}).get("completion_tokens")
        w_wall = res.get("wall_s")
        if w_ct and w_ttft and w_wall and w_wall > w_ttft:
            w_decode_wire = w_ct / (w_wall - w_ttft)
        else:
            w_decode_wire = None
        w_cached = ((res.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")

        if w_decode_wire is not None:
            workload_wire_speeds.append(w_decode_wire)

        pid_key = prompt_id
        if pid_key not in per_prompt_walls:
            per_prompt_walls[pid_key] = []
        per_prompt_walls[pid_key].append(res.get("wall_s", 0))
        all_wall_times.append((idx, res.get("wall_s", 0), lt.get("predicted_per_second")))

        if pid_key not in per_prompt_wire:
            per_prompt_wire[pid_key] = []
        if w_decode_wire is not None:
            per_prompt_wire[pid_key].append(w_decode_wire)
        all_wire_times.append((idx, w_decode_wire))

        rec = {
            "idx": idx, "kind": "workload", "prompt_id": prompt_id,
            "t_start": datetime.datetime.now().astimezone().isoformat(),
            "wall_s": res.get("wall_s"), "ok": ok,
            "error": res.get("error"),
            "finish_reason": res.get("finish_reason"),
            "usage": res.get("usage"), "last_timings": lt,
            "content_preview": content_preview,
            "ttft_s": w_ttft,
            "decode_wire_toks_s": w_decode_wire,
            "cached_tokens": w_cached,
        }
        with open(jln, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")

        idx += 1

    # Final canary
    fc_res = chat_completion(
        args.url,
        [{"role": "user", "content": CANARY_PROMPT}],
        256, extra={**effort_extra("none"), "temperature": 0}, timeout=args.timeout,
    )
    fc_combined = (fc_res.get("reasoning_content", "") or "") + "\x00" + (fc_res.get("content", "") or "")
    fc_h = hashlib.sha256(fc_combined.encode()).hexdigest()
    canary_hashes.append(fc_h)
    fc_rec = {
        "idx": idx, "kind": "canary", "prompt_id": "canary",
        "t_start": datetime.datetime.now().astimezone().isoformat(),
        "wall_s": fc_res.get("wall_s"), "ok": fc_res.get("ok", False),
        "hash": fc_h, "content": fc_res.get("content", ""),
        "reasoning_content": fc_res.get("reasoning_content", ""),
        "finish_reason": fc_res.get("finish_reason"),
        "usage": fc_res.get("usage"), "last_timings": fc_res.get("last_timings"),
    }
    with open(jln, "a") as f:
        f.write(json.dumps(fc_rec, default=str) + "\n")

    # Summary
    canary_unique = len(set(canary_hashes))
    decode_speeds = [s for s in workload_decode_speeds if s]
    draft_acceptance = draft_accepted_total / draft_n_total if draft_n_total else 0.0

    per_prompt_median = {}
    for pid, walls in per_prompt_walls.items():
        per_prompt_median[pid] = statistics.median(walls) if walls else 0

    n = len(all_wall_times)
    first_third = all_wall_times[:n // 3] if n else []
    last_third = all_wall_times[n * 2 // 3:] if n else []
    ft_speeds = [s for _, _, s in first_third if s]
    lt_speeds = [s for _, _, s in last_third if s]
    first_third_median = statistics.median(ft_speeds) if ft_speeds else 0
    last_third_median = statistics.median(lt_speeds) if lt_speeds else 0

    # Wire decode speed summaries
    non_none_wire = [s for s in workload_wire_speeds if s is not None]
    wire_min = min(non_none_wire) if non_none_wire else 0
    wire_median = statistics.median(non_none_wire) if non_none_wire else 0
    wire_max = max(non_none_wire) if non_none_wire else 0

    # Per-prompt median wire decode
    per_prompt_median_wire = {}
    for pid, wires in per_prompt_wire.items():
        per_prompt_median_wire[pid] = statistics.median(wires) if wires else 0

    # First/last third wire medians (mirror engine-side logic using indices from all_wire_times)
    nw = len(all_wire_times)
    ft_wire = all_wire_times[:nw // 3] if nw else []
    lt_wire = all_wire_times[nw * 2 // 3:] if nw else []
    ft_wire_speeds = [s for _, s in ft_wire if s is not None]
    lt_wire_speeds = [s for _, s in lt_wire if s is not None]
    first_third_wire_median = statistics.median(ft_wire_speeds) if ft_wire_speeds else 0
    last_third_wire_median = statistics.median(lt_wire_speeds) if lt_wire_speeds else 0

    summary = {
        "requests": idx,
        "failed": failed,
        "canaries": len(canary_hashes),
        "canary_unique": canary_unique,
        "stop_reason": stop_reason,
        "workload_decode_toks_s": {
            "min": min(decode_speeds) if decode_speeds else 0,
            "median": statistics.median(decode_speeds) if decode_speeds else 0,
            "max": max(decode_speeds) if decode_speeds else 0,
        },
        "workload_decode_wire_toks_s": {
            "min": wire_min,
            "median": wire_median,
            "max": wire_max,
        },
        "draft_acceptance": draft_acceptance,
        "per_prompt_median_wall_s": per_prompt_median,
        "first_third_median_decode_toks_s": first_third_median,
        "last_third_median_decode_toks_s": last_third_median,
        "per_prompt_median_decode_wire_toks_s": per_prompt_median_wire,
        "first_third_median_decode_wire_toks_s": first_third_wire_median,
        "last_third_median_decode_wire_toks_s": last_third_wire_median,
    }
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    verdict = "PASS" if failed == 0 and stop_reason == "duration" else "FAIL"
    result_line = f"RESULT SOAK {verdict} requests={idx} failed={failed} canary_unique={canary_unique} stop={stop_reason}"
    print(result_line, flush=True)
    return 0 if verdict == "PASS" else 1


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="xetest — LLM server test harness")
    parser.add_argument("--backend", choices=["xestrata", "vllm"], default="xestrata")
    parser.add_argument("--model", default="x")
    parser.add_argument("--container", default="xestrata-b70")
    parser.add_argument("--url", default="http://127.0.0.1:8095", help="Server base URL")
    parser.add_argument("--timeout", type=int, default=1800, help="HTTP timeout in seconds")
    sub = parser.add_subparsers(dest="command")

    p_canary = sub.add_parser("canary")
    p_canary.add_argument("--n", type=int, default=3)
    p_canary.add_argument("--effort", default="none")
    p_canary.add_argument("--max-tokens", type=int, default=256)
    p_canary.add_argument("--temperature", type=float, default=0.0)
    p_canary.add_argument("--interleave", action="store_true")
    p_canary.add_argument("--out", required=True)

    p_needle = sub.add_parser("needle")
    p_needle.add_argument("--sizes", default="8000,32000")
    p_needle.add_argument("--effort", default="none")
    p_needle.add_argument("--max-tokens", type=int, default=128)
    p_needle.add_argument("--depth", type=float, default=0.63)
    p_needle.add_argument("--seed", type=int, default=1)
    p_needle.add_argument("--out", required=True)

    p_soak = sub.add_parser("soak")
    p_soak.add_argument("--duration", type=int, default=1800)
    p_soak.add_argument("--canary-every", type=int, default=300)
    p_soak.add_argument("--seed", type=int, default=20261011)
    p_soak.add_argument("--effort", default="low")
    p_soak.add_argument("--out", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(2)

    global BACKEND, MODEL, CONTAINER
    BACKEND = args.backend
    MODEL = args.model
    CONTAINER = args.container

    if args.command == "canary":
        rc = cmd_canary(args)
    elif args.command == "needle":
        rc = cmd_needle(args)
    elif args.command == "soak":
        rc = cmd_soak(args)
    else:
        sys.exit(2)
    sys.exit(rc)


if __name__ == "__main__":
    main()
