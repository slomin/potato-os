#!/usr/bin/env python3
"""Gemma 4 multi-turn chat benchmark for Potato OS spike #274.

Usage:
    python3 tests/e2e/bench_gemma4_chat.py --host potato.local
    python3 tests/e2e/bench_gemma4_chat.py --host ssd.local --port 8080
"""
import argparse
import json
import time
import urllib.request
import urllib.error

CHAT_TURNS = [
    "What are the main differences between classical and quantum computing? Explain in detail.",
    "Can you explain quantum entanglement in simpler terms, with a concrete analogy?",
    "How might quantum computing affect modern cryptography and security?",
    "What's the current state of quantum error correction research?",
    "Summarize the key takeaways from our conversation in bullet points.",
]

def chat_completion(host, port, messages, max_tokens=512):
    """Send a chat completion request and return timing + response."""
    url = f"http://{host}:{port}/v1/chat/completions"
    payload = json.dumps({
        "model": "default",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "stream": False,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e), "wall_time": time.monotonic() - t0}
    wall = time.monotonic() - t0

    choice = body.get("choices", [{}])[0]
    usage = body.get("usage", {})
    timings = body.get("timings", {})

    return {
        "wall_time": round(wall, 2),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "prompt_tps": round(timings.get("prompt_per_second", 0), 2),
        "gen_tps": round(timings.get("predicted_per_second", 0), 2),
        "prompt_ms": round(timings.get("prompt_ms", 0), 1),
        "gen_ms": round(timings.get("predicted_ms", 0), 1),
        "reply": choice.get("message", {}).get("content", "")[:100],
    }

def get_status(host):
    """Get device status."""
    url = f"http://{host}/status"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}

def get_memory(host, sshpass="raspberry"):
    """Get memory info via SSH."""
    import subprocess
    try:
        result = subprocess.run(
            ["sshpass", "-p", sshpass, "ssh", "-o", "StrictHostKeyChecking=accept-new",
             f"pi@{host}", "free -m | grep -E 'Mem|Swap'"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return "unavailable"

def run_benchmark(host, port=1983):
    status = get_status(host)
    model = status.get("model", {}).get("filename", "unknown")
    rt = status.get("llama_runtime", {}).get("current", {})
    runtime = f"{rt.get('family', '?')} ({rt.get('llama_cpp_commit', '?')})"

    print(f"\n{'='*70}")
    print(f"Host:    {host}")
    print(f"Model:   {model}")
    print(f"Runtime: {runtime}")
    print(f"Memory:  {get_memory(host)}")
    print(f"{'='*70}")

    messages = []
    total_gen = 0
    results = []

    for i, user_msg in enumerate(CHAT_TURNS):
        messages.append({"role": "user", "content": user_msg})
        print(f"\n--- Turn {i+1}/{len(CHAT_TURNS)} ---")
        print(f"User: {user_msg[:80]}...")

        r = chat_completion(host, port, messages, max_tokens=512)
        if "error" in r:
            print(f"ERROR: {r['error']}")
            results.append(r)
            break

        total_gen += r["completion_tokens"]
        messages.append({"role": "assistant", "content": r.get("reply", "")})

        print(f"  Prompt:  {r['prompt_tokens']} tok, {r['prompt_tps']} t/s ({r['prompt_ms']}ms)")
        print(f"  Gen:     {r['completion_tokens']} tok, {r['gen_tps']} t/s ({r['gen_ms']}ms)")
        print(f"  Wall:    {r['wall_time']}s")
        print(f"  Reply:   {r['reply'][:80]}...")
        results.append(r)

    print(f"\n--- Summary ---")
    print(f"Total generated: {total_gen} tokens across {len(results)} turns")
    if results and "gen_tps" in results[0]:
        gen_rates = [r["gen_tps"] for r in results if "gen_tps" in r and r["gen_tps"] > 0]
        prompt_rates = [r["prompt_tps"] for r in results if "prompt_tps" in r and r["prompt_tps"] > 0]
        if gen_rates:
            print(f"Gen t/s:   min={min(gen_rates)}, max={max(gen_rates)}, avg={sum(gen_rates)/len(gen_rates):.1f}")
        if prompt_rates:
            print(f"Prompt t/s: min={min(prompt_rates)}, max={max(prompt_rates)}, avg={sum(prompt_rates)/len(prompt_rates):.1f}")
            if len(prompt_rates) > 1:
                print(f"  Turn 1 prompt: {prompt_rates[0]} t/s vs Turn 2+: {sum(prompt_rates[1:])/len(prompt_rates[1:]):.1f} t/s (caching effect)")
    print(f"Memory after: {get_memory(host)}")
    print()

    return {"host": host, "model": model, "runtime": runtime, "turns": results, "total_gen": total_gen}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=80)
    args = parser.parse_args()
    run_benchmark(args.host, args.port)
