import ollama
from typing import List
import os
import subprocess
import time
import signal

MODELS: List[str] = [
    "smollm:1.7b", "falcon3:7b", "orca-mini:7b", "mistral:7b", "llama3.2:latest", 
    "llama3:latest", "granite3.3:8b", "phi3.5:latest", "deepseek-r1:8b", "gemma:latest"
]


def start_ollama() -> subprocess.Popen:
    """
    Starts Ollama server as a background process on Windows.
    Returns the process handle.
    """
    print("Starting Ollama server...")

    # Start Ollama server quietly
    process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )

    # Give server time to initialize
    time.sleep(2)

    print("Ollama server started.\n")
    return process


def stop_ollama(process: subprocess.Popen):
    """
    Kills Ollama.exe or the started server.
    """
    print("\nStopping Ollama server...")

    # Kill the process we started
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT)
        process.terminate()
    except Exception:
        pass

    # Also kill any orphan Ollama.exe instances (safe cleanup)
    subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("Ollama server stopped.")


def stream_model_response(model: str, prompt: str, ID: str) -> None:
    """
    Save model response to a txt file.
    """
    print(f"\n=== Response from model: {model} ===")

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        with open("conversation/" + ID + ".txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== Response from model: {model} ===\n")
            f.write(f"{response['message']['content']}\n\n")

    except Exception as e:
        print(f"[Error] Model '{model}' failed: {e}")


def main() -> None:
    print("Multi-model Ollama Chat — type 'exit' to quit.\n")

    # Start Ollama server
    ollama_process = start_ollama()

    try:
        ID_session = input("Enter session ID (or press Enter to skip): ").strip()
        if ID_session:
            os.makedirs("conversation", exist_ok=True)
            if not os.path.exists("conversation/" + ID_session + ".txt"):
                open("conversation/" + ID_session + ".txt", "w").close()

        while True:
            prompt = input("Enter your prompt: ")

            if prompt.lower().strip() == "exit":
                print("Exiting...")
                break

            with open("conversation/" + ID_session + ".txt", "a", encoding="utf-8") as f:
                f.write(f"User: {prompt}\n")

            for model in MODELS:
                stream_model_response(model, prompt, ID_session)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        # Stop Ollama when done
        stop_ollama(ollama_process)


if __name__ == "__main__":
    main()
