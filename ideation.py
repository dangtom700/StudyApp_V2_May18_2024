import gradio as gr
import json
import os
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
import subprocess

model_names = [
    "llama3:latest", "llama3.2:latest", "phi3.5:latest",
    "gemma:latest", "deepseek-r1:8b", "granite3.3:8b"
]

SESSION_ID = "default"
LOG_FILE = "PROMPT.txt"
FAV_FILE = "data\\fav.txt"
os.makedirs("data", exist_ok=True)

# Chain builder
def build_chain(name):
    llm = OllamaLLM(model=name)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You're helping me to brainstorm new ideas."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
    chain_with_prompt = prompt | llm
    memory_path = f"data/memory_{name.replace(':', '_')}.json"
    if not os.path.exists(memory_path): open(memory_path, "w").write("[]")
    message_history = FileChatMessageHistory(memory_path)
    chain = RunnableWithMessageHistory(
        chain_with_prompt,
        lambda session_id: message_history,
        input_messages_key="input",
        history_messages_key="history"
    )
    return chain, memory_path, message_history

# Purge memory
def purge_memory(name):
    memory_path = f"data/memory_{name.replace(':', '_')}.json"
    if os.path.exists(memory_path): os.remove(memory_path)
for name in model_names: purge_memory(name)

# Init chains
chains = {name: build_chain(name) for name in model_names}

def stop_model(name): subprocess.run(["ollama", "stop", name])

# Core logic for querying all models
def query_all_models(user_input):
    results = {}
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"\nYou: {user_input}\n")
        for name, (chain, memory_path, history) in chains.items():
            try:
                response = chain.invoke({"input": user_input}, config={"configurable": {"session_id": SESSION_ID}})
                if "deepseek" in name.lower():
                    # Replace <think> tags with markdown-friendly formatting
                    response = response.replace("<think>", "### Thinking\n").replace("</think>", "\n---\n### Result\n")
            except Exception as e:
                response = f"[Error from {name}]: {e}"

            stop_model(name)
            log.write(f"{name}: {response}\n")
            results[name] = {
                "response": response,
                "memory": json.dumps(json.load(open(memory_path, "r")), indent=2),
                "memory_path": memory_path
            }
    return results


# App UI
with gr.Blocks() as demo:
    gr.Markdown("# 🔍 Multi-LLM Ideation Comparator")

    user_input = gr.Textbox(label="Your prompt")
    submit_btn = gr.Button("Submit")

    status = gr.Textbox(visible=False)
    model_outputs = {}

    with gr.Tabs():
        for name in model_names:
            with gr.Tab(label=name):
                chat_out = gr.Markdown(label="Response")
                mem_edit = gr.Textbox(label="Edit Memory (JSON)", lines=8)
                save_btn = gr.Button("💾 Save Memory")
                fav_btn = gr.Button("⭐ Favorite")
                msg = gr.Textbox(visible=False)

                model_outputs[name] = {
                    "response_box": chat_out,
                    "memory_box": mem_edit,
                    "save_btn": save_btn,
                    "fav_btn": fav_btn,
                    "msg": msg,
                }

    state = gr.State({})  # holds last responses

    # Submit handler
    def handle_submit(prompt):
        results = query_all_models(prompt)
        return [results] + [results[name]["response"] for name in model_names] + [results[name]["memory"] for name in model_names]

    submit_btn.click(
        fn=handle_submit,
        inputs=[user_input],
        outputs=[state] + [model_outputs[name]["response_box"] for name in model_names] +
                [model_outputs[name]["memory_box"] for name in model_names]
    )

    # Save memory handlers
    for name in model_names:
        def save_memory(json_text, name=name):
            path = f"data/memory_{name.replace(':', '_')}.json"
            try:
                json.dump(json.loads(json_text), open(path, "w"))
                return f"{name} memory saved."
            except Exception as e:
                return f"Error saving {name}: {e}"

        model_outputs[name]["save_btn"].click(
            fn=save_memory,
            inputs=model_outputs[name]["memory_box"],
            outputs=model_outputs[name]["msg"]
        )

        def favorite_fn(state, name=name):
            data = state[name]
            with open(FAV_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{name}]\nPrompt: {user_input.value}\nResponse: {data['response']}\n\n")
            return f"Favorited {name}!"

        model_outputs[name]["fav_btn"].click(
            fn=favorite_fn,
            inputs=[state],
            outputs=model_outputs[name]["msg"]
        )

demo.launch()
