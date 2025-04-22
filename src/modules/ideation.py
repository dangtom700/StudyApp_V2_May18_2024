import json
import os
import subprocess
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# --- Config ---
model_names = [
    "llama3:latest", "llama3.2:latest", "phi3.5:latest",
    "gemma:latest", "deepseek-r1:8b", "granite3.3:8b"
]

SESSION_ID = "default"
DATA_DIR = "data"
LOG_FILE = os.path.join(DATA_DIR, "PROMPT.txt")
FAV_FILE = os.path.join(DATA_DIR, "fav.txt")
os.makedirs(DATA_DIR, exist_ok=True)

# --- Functions ---
def build_chain(name):
    llm = OllamaLLM(model=name)
    prompt = ChatPromptTemplate.from_messages("You are helping me to explore different aspects of my questions.",
                                               MessagesPlaceholder(variable_name="input"))
    chain_with_prompt = prompt | llm
    memory_path = os.path.join(DATA_DIR, f"memory_{name.replace(':', '_')}.json")
    if not os.path.exists(memory_path):
        with open(memory_path, "w") as f:
            f.write("[]")
    message_history = FileChatMessageHistory(memory_path)
    chain = RunnableWithMessageHistory(
        chain_with_prompt,
        lambda session_id: message_history,
        input_messages_key="input",
        history_messages_key="history"
    )
    return chain, memory_path, message_history

def purge_memory(name):
    memory_path = os.path.join(DATA_DIR, f"memory_{name.replace(':', '_')}.json")
    if os.path.exists(memory_path):
        os.remove(memory_path)

def stop_model(name):
    subprocess.run(["ollama", "stop", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def query_all_models(user_input):
    results = {}
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"\nYou: {user_input}\n")
        for name, (chain, memory_path, _) in chains.items():
            print(f"\n[INFO] Querying model: {name}")
            try:
                response = chain.invoke({"input": user_input}, config={"configurable": {"session_id": SESSION_ID}})
                if "deepseek" in name.lower():
                    response = response.replace("<think>", "### Thinking\n").replace("</think>", "\n---\n### Result\n")
            except Exception as e:
                response = f"[Error from {name}]: {e}"
            stop_model(name)
            log.write(f"{name}: {response}\n")
            print(f"[{name} Response]\n{response}")
            results[name] = {
                "response": response,
                "memory_path": memory_path
            }
    return results

def save_memory(name, new_json_text):
    path = os.path.join(DATA_DIR, f"memory_{name.replace(':', '_')}.json")
    try:
        json.dump(json.loads(new_json_text), open(path, "w"), indent=2)
        print(f"[INFO] {name} memory saved.")
    except Exception as e:
        print(f"[ERROR] Saving {name} memory failed: {e}")

def favorite_response(name, prompt, response):
    with open(FAV_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{name}]\nPrompt: {prompt}\nResponse: {response}\n\n")
    print(f"[INFO] Favorited response from {name}.")

# --- Main ---
if __name__ == "__main__":
    # Purge memories
    for name in model_names:
        purge_memory(name)

    # Build chains
    chains = {name: build_chain(name) for name in model_names}

    while True:
        print("\n--- Multi-Model Prompting ---")
        user_input = input("Enter your prompt (or type 'exit'): ").strip()
        if user_input.lower() in ("exit", "quit"):
            break

        results = query_all_models(user_input)

        for name in model_names:
            response = results[name]["response"]
            memory_path = results[name]["memory_path"]

            print(f"\n--- [{name}] Options ---")
            action = input("Type [f] to favorite, [e] to edit memory, or [Enter] to continue: ").strip().lower()

            if action == "f":
                favorite_response(name, user_input, response)

            elif action == "e":
                try:
                    print(f"\nCurrent memory for {name}:\n")
                    with open(memory_path, "r", encoding="utf-8") as f:
                        print(f.read())
                    new_json = input("\nPaste new memory JSON:\n")
                    save_memory(name, new_json)
                except Exception as e:
                    print(f"[ERROR] Could not edit memory: {e}")
