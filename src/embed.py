import os
import sqlite3
import sys
from langchain_core.documents import Document
from typing import Annotated, Sequence, TypedDict
from operator import add as add_messages
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.tools import tool

from modules.path import chunk_database_path, DB_DIR, OLLAMA_BASE_URL, EMBEDDING_MODEL, LLM_MODEL, data_folder

def ingest_from_db():
    print(f"Initializing Ollama embeddings ({EMBEDDING_MODEL})...")
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
        keep_alive=0 # Unload from VRAM immediately after use to save memory
    )
    
    # Check if we should resolve DB_DIR relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    persist_dir = DB_DIR
    if not os.path.isabs(persist_dir):
        persist_dir = os.path.join(project_root, persist_dir)
        
    print(f"Connecting to vector database in {persist_dir}...")
    vectorstore = Chroma(
        persist_directory=persist_dir, 
        embedding_function=embeddings
    )
    
    print(f"Connecting to SQLite database at {chunk_database_path}...")
    if not os.path.exists(chunk_database_path):
        print(f"Error: SQLite database not found at {chunk_database_path}")
        return

    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM pdf_chunks")
        total_chunks = cursor.fetchone()[0]
        print(f"Found {total_chunks} chunks in the database.")
        
        batch_size = 10  # Process in batches to manage memory
        offset_file = os.path.join(data_folder, "embed_offset.txt")
        offset = 0
        if os.path.exists(offset_file):
            try:
                with open(offset_file, "r") as f:
                    offset = int(f.read().strip())
                    print(f"Resuming ingestion from offset: {offset}")
            except Exception as e:
                print(f"Could not read offset file, starting from 0: {e}")
                offset = 0
        
        while True:
            cursor.execute(
                "SELECT file_name, chunk_id, chunk_text FROM pdf_chunks LIMIT ? OFFSET ?", 
                (batch_size, offset)
            )
            rows = cursor.fetchall()
            
            if not rows:
                break
                
            docs = []
            ids = []
            for row in rows:
                file_name, chunk_id, chunk_text = row
                doc = Document(
                    page_content=chunk_text,
                    metadata={"source": file_name, "chunk_id": chunk_id}
                )
                docs.append(doc)
                ids.append(f"{file_name}_{chunk_id}")
                
            print(f"Processing batch of {len(docs)} chunks (Offset: {offset}/{total_chunks})...")
            # add_documents with ids prevents duplicate ingestion
            vectorstore.add_documents(documents=docs, ids=ids)
            
            offset += batch_size
            with open(offset_file, "w") as f:
                f.write(str(offset))
            
        print("Ingestion complete! The vector database is updated.")
        if os.path.exists(offset_file):
            os.remove(offset_file)
    except Exception as e:
        print(f"Error reading from SQLite database: {e}")
    finally:
        conn.close()

# Define the state with message appending behavior
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Initialize components
embeddings = OllamaEmbeddings(
    model=EMBEDDING_MODEL, 
    base_url=OLLAMA_BASE_URL,
    keep_alive=0 # Unload from VRAM immediately after use
)
vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# Define the retriever as a tool
@tool
def retriever_tool(query: str) -> str:
    """
    This tool searches and returns information from the loaded document database.
    Use this tool whenever you need to look up facts, context, or data to answer the user's question.
    """
    docs = retriever.invoke(query)
    if not docs:
        return "I found no relevant information in the documents."
    
    results = []
    for i, doc in enumerate(docs):
        results.append(f"Document {i+1}:\n{doc.page_content}")
    return "\n\n".join(results)

tools = [retriever_tool]
tools_dict = {t.name: t for t in tools}

# Initialize the local LLM and bind tools
llm = ChatOllama(
    model=LLM_MODEL, 
    base_url=OLLAMA_BASE_URL,
    num_ctx=8192,
    keep_alive=0
).bind_tools(tools)

system_prompt = """
You are an intelligent AI assistant.
Use the retriever tool available to answer questions based on the knowledge base.
You can make multiple calls if needed.
If you need to look up some information before asking a follow up question, you are allowed to do that!
Please always cite the specific parts of the documents you use in your answers.
"""

def call_llm(state: AgentState):
    """Function to call the LLM with the current state."""
    messages = list(state['messages'])
    # Ensure system prompt is present
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=system_prompt)] + messages
        
    message = llm.invoke(messages)
    return {'messages': [message]}

def take_action(state: AgentState):
    """Execute tool calls from the LLM's response."""
    last_message = state['messages'][-1]
    results = []
    
    if hasattr(last_message, 'tool_calls'):
        for t in last_message.tool_calls:
            print(f"\n[Agent executing tool: {t['name']} with query: {t['args'].get('query', 'No query provided')}]")
            
            if t['name'] not in tools_dict:
                print(f"Tool: {t['name']} does not exist.")
                result = "Incorrect Tool Name, Please Retry and Select tool from List of Available tools."
            else:
                try:
                    # Execute tool
                    result = tools_dict[t['name']].invoke(t['args'])
                except Exception as e:
                    result = f"Error executing tool: {e}"
                    
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))

    return {'messages': results}

def should_continue(state: AgentState):
    """Check if the last message contains tool calls."""
    last_message = state['messages'][-1]
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        return "take_action"
    return END

def main():
    # Force UTF-8 encoding for standard output to prevent crashes with emojis on Windows
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    if not os.path.exists(DB_DIR):
        print(f"Warning: Vector database directory '{DB_DIR}' not found.")
        print("Please run 'python ingest.py' first to build the semantic search index.")
        sys.exit(1)

    print("\n" + "="*50)
    print("Semantic Search Engine Initialized")
    print("Agentic RAG Mode: ON")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("="*50 + "\n")
    
    # We keep a rolling history for the session if we want, or reset per question
    # We will reset per question like the reference snippet
    while True:
        try:
            query = input("What is your question: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if query.lower() in ['quit', 'exit', 'q']:
            break
            
        if not query.strip():
            continue
            
        print("\nThinking...")
        messages = [HumanMessage(content=query)]
        
        # Invoke the graph
        result = app.invoke({"messages": messages})
        
        print("\n=== ANSWER ===")
        print(result['messages'][-1].content)
        print("="*50 + "\n")

if __name__ == "__main__":
    ingest_from_db()
    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("llm", call_llm)
    workflow.add_node("take_action", take_action)

    workflow.add_edge(START, "llm")
    workflow.add_conditional_edges(
        "llm",
        should_continue,
        {"take_action": "take_action", END: END}
    )
    workflow.add_edge("take_action", "llm")

    app = workflow.compile()
    main()