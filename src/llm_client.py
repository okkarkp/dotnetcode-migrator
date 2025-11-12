import requests, json

LLM_ENDPOINT = "http://localhost:18081/v1/chat/completions"

def query_llm(prompt: str, max_tokens=800, temperature=0.2):
    """
    Send a chat completion request to the local Phi-4 server (OpenAI-compatible endpoint).
    Returns model's text response.
    """
    payload = {
        "model": "Phi-4-mini-instruct-Q3_K_S.gguf",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    try:
        r = requests.post(LLM_ENDPOINT, json=payload, timeout=180)
        r.raise_for_status()
        data = r.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        return f"(no response from model: {json.dumps(data)})"
    except Exception as e:
        return f"LLM call failed: {e}"
