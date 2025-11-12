import os, uvicorn
from llama_cpp.server.app import create_app
from llama_cpp.server.settings import Settings

def main():
    model_path = os.getenv("MODEL_PATH", "/opt/oss-migrate/llm-planner-ai/models/Phi-4-mini-instruct-Q3_K_S.gguf")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "18081"))
    n_ctx = int(os.getenv("N_CTX", "8192"))
    n_threads = int(os.getenv("N_THREADS", "4"))

    settings = Settings(model=model_path, n_ctx=n_ctx, n_threads=n_threads)
    app = create_app(settings)
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
