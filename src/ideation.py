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


def stream_model_response(model: str, prompt: str, ID: str, num:int) -> None:
    """
    Save model response to a txt file.
    """
    print(f"=== Response from model: {model} ===")

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        with open("conversation/" + ID + ".txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== Response {num} ===\n\n")
            f.write(f"{response['message']['content']}\n\n")

    except Exception as e:
        print(f"[Error] Model '{model}' failed: {e}")

def update_script(used_prompt: str) -> None:
    """
    Remove a specific prompt from the 'prompts' list inside this script.
    Safely rewrites the current file.
    """

    script_path = os.path.abspath(__file__)

    with open(script_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    inside_prompt_block = False

    for line in lines:
        stripped = line.strip()

        # Detect start of prompts list
        if stripped.startswith("prompts: List[str] = ["):
            inside_prompt_block = True
            new_lines.append(line)
            continue

        # Detect end of prompts list
        if inside_prompt_block and stripped.startswith("]"):
            inside_prompt_block = False
            new_lines.append(line)
            continue

        # If inside list, skip the used prompt
        if inside_prompt_block:
            # A prompt line should look like: "    \"text here\","
            if used_prompt in stripped.strip('",'):
                # Skip this line (remove prompt)
                continue

        # Default: keep line
        new_lines.append(line)

    # Write updated script
    with open(script_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def main() -> None:
    print("Multi-model Ollama Chat — type 'exit' to quit.\n")
    prompts: List[str] = [
        
    ]

    # Start Ollama server
    ollama_process = start_ollama()
    limiter = len(prompts)

    try:
        ID_session = input("Enter session ID (or press Enter to skip): ").strip()
        if ID_session:
            os.makedirs("conversation", exist_ok=True)
            if not os.path.exists("conversation/" + ID_session + ".txt"):
                open("conversation/" + ID_session + ".txt", "w").close()

        for prompt in prompts[:limiter]: # Limit number of prompts for testing
            print(f"\nUser Prompt: {prompt}")
            with open("conversation/" + ID_session + ".txt", "a", encoding="utf-8") as f:
                f.write(f"User: {prompt}\n")

            for index in range(len(MODELS)):
                model = MODELS[index]
                stream_model_response(model, prompt, ID_session, index+1)

            update_script(prompt)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        # Stop Ollama when done
        stop_ollama(ollama_process)


if __name__ == "__main__":
    main()
