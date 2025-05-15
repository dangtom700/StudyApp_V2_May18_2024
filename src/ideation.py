import os
import re
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

def main():
    user_input = input("Your prompt: ").strip()
    session_id = "my_session"

    # Save the prompt
    with open("PROMPT.txt", "w") as f:
        f.write(user_input)
        f.write("\n\n\n")

    # Clear the conversation directory
    for file in os.listdir(conversation_dir):
        if file.startswith(session_id):
            os.remove(os.path.join(conversation_dir, file))

    for model_name in model_names:
        print(f"\n--- {model_name} ---")
        chain = create_chain(model_name, session_id)

        try:
            response = chain.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config={"configurable": {"session_id": session_id}}
            )

            # Clean the response to match utf-8 encoding
            response = re.sub(r'\\u[0-9a-fA-F]{3,4}', ' ', response) # Remove any Unicode escape sequences like \u256 or \uXXXX
            response = response.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore") # Remove any characters not encodable in UTF-8
            response = re.sub(r' +', ' ', response) # Remove extra spaces
            
            with open("PROMPT.txt", "a") as f:
                f.write(f"------\n")
                f.write(response)
                f.write("\n\n\n")
        except Exception as e:
            print(f"Error with {model_name}: {e}")


if __name__ == "__main__":
    main()
