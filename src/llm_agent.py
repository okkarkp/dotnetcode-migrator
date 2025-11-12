from llama_cpp import Llama
class LocalLLM:
    def __init__(self, model_path, ctx=2048, threads=4):
        self.llm=Llama(model_path=model_path,n_ctx=ctx,n_threads=threads)
    def summarize(self,project_info,build_diag,rule_hits):
        prompt=f"""
You are an offline .NET 6→8 upgrade advisor.
Analyze project info, diagnostics, and rules. Give concise bullet recommendations.

PROJECT:
{project_info}

DIAGNOSTICS:
{build_diag}

RULES:
{rule_hits}
"""
        res=self.llm(prompt,max_tokens=400,temperature=0.2)
        return res["choices"][0]["text"].strip()
