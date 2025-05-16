import os
import subprocess
import re
from datetime import datetime
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage

# --- Config ---
model_names = [
    "llama3:latest", "llama3.2:latest", "phi3.5:latest",
    "gemma:latest", "deepseek-r1:8b"
]
conversation_dir = "conversations"
os.makedirs(conversation_dir, exist_ok=True)

# --- Functions ---
def create_chain(model_name, session_id):
    llm = OllamaLLM(model=model_name)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"You are {model_name}. Respond concisely and helpfully."),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm
    history = FileChatMessageHistory(f"{conversation_dir}/{session_id}_{model_name.replace(':', '_')}.json")
    return RunnableWithMessageHistory(chain, lambda session_id: history, input_messages_key="messages")

def one_turn_conversation(session_id: str, user_input: str) -> None:
    for model_name in model_names:
        print(f"\n--- {model_name} ---")

        try:
            # Ensure the model is downloaded
            subprocess.run(["ollama", "run", model_name], stdout=subprocess.PIPE, check=True)

            # Create and invoke chain
            chain = create_chain(model_name, session_id)
            raw_response = chain.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config={"configurable": {"session_id": session_id}}
            )
            
            subprocess.run(["ollama", "stop", model_name], stdout=subprocess.PIPE, check=True)

            # Clean response
            response_text = re.sub(r'\\u[0-9a-fA-F]{3,4}', ' ', raw_response)
            response_text = response_text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
            response_text = re.sub(r' +', ' ', response_text)

            # Save to file
            with open("PROMPT.txt", "a", encoding="utf-8") as f:
                f.write(f"------------\n")
                f.write(response_text)
                f.write("\n\n")
            # Debug: print out the number of file under conversations folder
            print(f"Number of files under {conversation_dir}: {len(os.listdir(conversation_dir))}")
        except Exception as e:
            print(f"Error with {model_name}: {e}")

if __name__ == "__main__":
    # ---------- Setup ----------

    # Get the session ID
    session_id = input("Session ID: ").strip("Session ID: ")
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # Start a fresh conversation?
    fresh_conversation = input("Start a fresh conversation? (y/n): ").strip().lower()
    if fresh_conversation == "y":
        # Delete conversation files that start with the session ID
        for file in os.listdir(conversation_dir):
            if file.startswith(session_id):
                os.remove(os.path.join(conversation_dir, file))
        # Clear the output file
        with open("PROMPT.txt", "w", encoding="utf-8") as f:
            f.write("")

    # ---------- Conversation ----------
    while True:
        user_input = input("Your prompt: ").strip()
        # Exit if the user inputs "exit"
        if user_input == "exit":
            break

        # Save the prompt
        with open("PROMPT.txt", "a", encoding="utf-8") as f:
            f.write(user_input)
            f.write("\n\n")

        one_turn_conversation(session_id=session_id, user_input=user_input)