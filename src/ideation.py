import ollama
from typing import List, Dict, Any
import os
import subprocess
import time
import signal
import json

from datetime import datetime
from modules.path import data_folder

MODELS: List[str] = [
    "smollm:1.7b", "falcon3:7b", "orca-mini:7b", "mistral:7b",
    "llama3.2:latest", "granite3.3:8b", "ministral-3:latest",
    "phi3.5:latest", "deepseek-r1:8b", "gemma:latest"
]

PROMPTS_FILE = os.path.join(data_folder, "prompts.json")
COMPLETED_MODELS_FILE = os.path.join(data_folder, "completed_models.txt")
RESUME_STATE_FILE = os.path.join(data_folder, "resume_state.json")


def start_ollama() -> subprocess.Popen:
    """
    Starts Ollama server as a background process on Windows.
    Returns the process handle.
    """
    print("Starting Ollama server...")
    process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    time.sleep(2)
    print("Ollama server started.\n")
    return process

def stop_ollama(process: subprocess.Popen):
    """
    Kills Ollama.exe or the started server.
    """
    print("\nStopping Ollama server...")
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT)
        process.terminate()
    except Exception:
        pass
    subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Ollama server stopped.")


def load_prompts() -> List[str]:
    if not os.path.exists(PROMPTS_FILE):
        return []
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_completed_models() -> List[str]:
    if not os.path.exists(COMPLETED_MODELS_FILE):
        return []
    with open(COMPLETED_MODELS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_completed_model(model: str):
    with open(COMPLETED_MODELS_FILE, "a", encoding="utf-8") as f:
        f.write(model + "\n")

def load_resume_state() -> Dict[str, Any]:
    if not os.path.exists(RESUME_STATE_FILE):
        return {}
    try:
        with open(RESUME_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_resume_state(state: Dict[str, Any]):
    with open(RESUME_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


def main() -> None:
    print("Multi-model Ollama Chat — iteration by model.\n")
    
    prompts = load_prompts()
    if not prompts:
        print(f"Error: {PROMPTS_FILE} not found or empty.")
        return

    # Start Ollama server
    ollama_process = start_ollama()

    try:
        ID_session = input("Enter session ID (or press Enter to skip): ").strip()
        os.makedirs("conversation", exist_ok=True)
        if not ID_session:
            ID_session = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            print(f"Session ID set to current timestamp: {ID_session}")

        session_file = f"conversation/{ID_session}.txt"
        if not os.path.exists(session_file):
            open(session_file, "w").close()

        completed_models = load_completed_models()
        resume_state = load_resume_state()
        
        for model in MODELS:
            if model in completed_models:
                print(f"Skipping model: {model} (already completed all prompts)")
                continue

            print(f"\n======================================")
            print(f"Starting model: {model}")
            print(f"======================================")
            
            # Check if we have a resume state for this model
            completed_prompts_count = 0
            conversation_history = []
            
            if resume_state.get("model") == model:
                completed_prompts_count = resume_state.get("completed_prompts", 0)
                conversation_history = resume_state.get("history", [])
                print(f"Resuming {model} from prompt {completed_prompts_count + 1}/{len(prompts)}")
            else:
                # Starting a fresh model, reset resume state
                resume_state = {"model": model, "completed_prompts": 0, "history": []}
                save_resume_state(resume_state)

            with open(session_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n================ MODEL: {model} ================\n\n")

            for i in range(completed_prompts_count, len(prompts)):
                prompt = prompts[i]
                print(f"\n[{model}] Prompt {i+1}/{len(prompts)}: {prompt}")
                
                conversation_history.append({"role": "user", "content": prompt})

                try:
                    response = ollama.chat(
                        model=model,
                        messages=conversation_history,
                        stream=False,
                    )
                    
                    reply_content = response['message']['content']
                    conversation_history.append({"role": "assistant", "content": reply_content})
                    
                    with open(session_file, "a", encoding="utf-8") as f:
                        f.write(f"\n--- User Prompt {i+1} ---\n{prompt}\n")
                        f.write(f"\n--- Model Response {i+1} ---\n{reply_content}\n")
                    
                    # Update resume state after successful completion of a prompt
                    resume_state["completed_prompts"] = i + 1
                    resume_state["history"] = conversation_history
                    save_resume_state(resume_state)
                    
                except Exception as e:
                    print(f"[Error] Model '{model}' failed on prompt {i+1}: {e}")
                    print("You can restart the script to resume from this point.")
                    return  # Stop execution so the user can fix the issue and resume
                
            # If we reached here, the model has completed all prompts
            save_completed_model(model)
            print(f"\nModel {model} completed all prompts successfully.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        # Stop Ollama when done
        stop_ollama(ollama_process)

if __name__ == "__main__":
    main()
