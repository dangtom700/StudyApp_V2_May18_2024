from langchain_ollama import OllamaLLM
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableMap
from langchain_community.chat_message_histories import FileChatMessageHistory
import subprocess

# Define model names
model_names = [
    "llama3:latest",
    "phi3:mini",
    "gemma:latest",
    "mistral:latest",
    "gemma3:1b",
    "llama3.2:latest"
]

# Set up models + memory-backed chains
models = {}
for name in model_names:
    llm = OllamaLLM(model=name)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You're a helpful assistant."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])

    # Create prompt + model chain
    chain_with_prompt = prompt | llm

    # Each model has its own memory file
    memory_path = f"data\\memory_{name.replace(':', '_')}.json"
    message_history = FileChatMessageHistory(memory_path)

    # Create message-history-wrapped runnable
    chain = RunnableWithMessageHistory(
        chain_with_prompt,
        lambda session_id: message_history,
        input_messages_key="input",
        history_messages_key="history"
    )

    models[name] = chain

# Start minimal log
log_file = "PROMPT.txt"

# Clear memory files
for name in model_names:
    memory_path = f"data\\memory_{name.replace(':', '_')}.json"
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write("[]")

# Clear log
with open(log_file, "w", encoding="utf-8") as f:
    f.write("")

user_input = input("Question: ").strip()

while user_input != "exit":

    # Run each model
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\nQuestion: {user_input}\n")

        for model_name, chain in models.items():
            print(f"\n{model_name} responding...")
            try:
                response = chain.invoke(
                    {"input": user_input},
                    config={"configurable": {"session_id": "default"}}
                )
            except Exception as e:
                response = f"[Error from {model_name}]: {str(e)}"
            # Terminate the running model using ollama-cli
            subprocess.run(["ollama", "stop", model_name])
            f.write(f"\n{response}\n\n--------------------------------------------------------------------\n\n")

    user_input = input("You: ").strip()

# Clear memory files
for name in model_names:
    memory_path = f"data\\memory_{name.replace(':', '_')}.json"
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write("[]")