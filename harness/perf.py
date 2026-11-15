import json, time, urllib.request, sys, threading, random
B="http://127.0.0.1:8200/v1/completions"
def prompt(seed):
    r=random.Random(seed); w="time river house system light number water story market energy".split()
    return " ".join(r.choice(w) for _ in range(420))
def one(seed, out):
    body={"model":"ripple-65b-gptq-sd","prompt":prompt(seed),"max_tokens":256,"min_tokens":256,"ignore_eos":True,"temperature":0,"stream":True,"stream_options":{"include_usage":True}}
    t0=time.time(); first=None; n=0
    with urllib.request.urlopen(urllib.request.Request(B,json.dumps(body).encode(),{"Content-Type":"application/json"}),timeout=600) as resp:
        for line in resp:
            if line.startswith(b"data: ") and b"[DONE]" not in line:
                d=json.loads(line[6:])
                if d.get("choices") and d["choices"][0].get("text"):
                    if first is None: first=time.time()
                if d.get("usage"): n=d["usage"]["completion_tokens"]; pt=d["usage"]["prompt_tokens"]
    t1=time.time(); out.append((first-t0, (t1-first)/(n-1), n, pt, t1-t0))
for c in (1,4):
    for trial in range(2):
        out=[]; ts=[threading.Thread(target=one,args=(1000*c+10*trial+i,out)) for i in range(c)]
        t0=time.time(); [t.start() for t in ts]; [t.join() for t in ts]; wall=time.time()-t0
        ttft=sum(o[0] for o in out)/c; tpot=sum(o[1] for o in out)/c; toks=sum(o[2] for o in out)
        print(f"c={c} trial={trial} prompt_tok={out[0][3]} TTFT={ttft*1000:.0f}ms TPOT={tpot*1000:.1f}ms per-stream={1/tpot:.2f} tok/s aggregate={toks/wall:.1f} tok/s", flush=True)
