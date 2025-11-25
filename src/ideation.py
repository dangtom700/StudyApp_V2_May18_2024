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
    print(f"\n=== Response from model: {model} ===")

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

def upadte_script(prompt: str) -> None:
    # Remove a prompt from the script after it has been used
    with open(__file__, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(__file__, "w", encoding="utf-8") as f:
        inside_prompts = False
        for line in lines:
            if line.strip().startswith("prompts: List[str] = ["):
                inside_prompts = True
                f.write(line)
                continue
            if inside_prompts:
                if line.strip() == "]":
                    inside_prompts = False
                    f.write(line)
                    continue
                if line.strip().startswith(f'"{prompt}"'):
                    continue  # Skip this prompt
            f.write(line)

def main() -> None:
    print("Multi-model Ollama Chat — type 'exit' to quit.\n")
    prompts: List[str] = [
        "Contrast the core philosophical and spatial principles of Ebenezer Howard's Garden City Movement with Le Corbusier's Radiant City (Ville Radieuse). What is the lasting legacy of each today? How have these ideas influenced contemporary urban planning and design?",
        "What was the Sanitary Movement of the 19th century, and how did its focus on public health and infrastructure fundamentally change the role of city government in planning?",
        "Explain Jane Jacobs' central thesis in The Death and Life of Great American Cities. What are \"eyes on the street,\" and why are they critical to her concept of a vibrant, safe city"
        "Who was Robert Moses, and what is his legacy regarding the impact of large-scale infrastructure policy on urban neighborhoods, specifically in New York?",
        "Describe the principles of New Urbanism. How does this movement address issues of urban sprawl, walkability, and community design? Provide examples of New Urbanist developments.",
        "What are the main objectives of Environmental Planning within urban contexts? How do planners integrate sustainability and ecological considerations into urban development projects?",
        "Analyze the grid plan of Washington D.C. (L'Enfant Plan) and compare it to the orthogonal grid of a city like Barcelona's Eixample district (Cerdà Plan). How do the different grid geometries affect public space and traffic flow?",
        "Examine Brasília, Brazil. What were the key modernist principles applied by Lúcio Costa and Oscar Niemeyer? What unintended social or functional problems arose from this planning approach?", 
        "Describe the planning history of Singapore. What innovative planning and policy strategies has this city-state used to manage high density, transportation, and green space effectively?",
        "Research the concept of the \"15-Minute City.\" What are its core planning metrics and goals? What are the main political or social criticisms leveled against this concept?",
        "How does the concept of Tactical Urbanism differ from traditional, large-scale planning? Provide an example of a tactical urbanism project and its potential long-term impact on a neighborhood.",
        "Investigate a modern, influential public space like Superkilen in Copenhagen or The Goods Line in Sydney. How does its design actively promote social interaction and cultural diversity in a way that a traditional park might not?",
        "What is Zoning, and what are the primary legal and economic rationales behind it? Contrast Euclidean zoning (conventional) with a more modern approach like Form-Based Codes.",
        "Explain the concept of Gentrification in the context of urban policy. How might a successful urban design project (e.g., a new park or transit line) unintentionally contribute to displacement, and what policy tools (e.g., Inclusionary Zoning) can mitigate this?",
        "How does transportation planning—specifically the allocation of space for automobiles versus public transit/bicycles—directly impact a city's economic vitality and environmental sustainability? Use the example of a Congestion Charge policy (like in London or Singapore) to illustrate.",
        "How does the urban geometry of a street (e.g., building height-to-street width ratio, sidewalk width) influence a person's sense of comfort and the likelihood of spontaneous social interaction (propinquity)?",
        "Discuss the psychological concept of Biophilia in the context of urban design. How can integrating features like street trees, green roofs, and access to water alleviate stress and improve mental well-being for city residents?",
        "What is Defensible Space Theory (Oscar Newman)? How does the architectural and site design of housing developments influence resident safety, and why is this concept controversial in modern planning?",
        "Describe how a Geographic Information System (GIS) is used as a technical tool in urban planning. Give three specific examples of spatial analyses (e.g., buffer analysis, overlay) a planner might use GIS for.",
        "What is the fundamental concept of Density in planning, and why is it often misunderstood by the public? Differentiate between Floor Area Ratio (FAR) and Dwelling Units per Acre (DUA).",
        "How does the geometry of an intersection—specifically the presence or absence of \"free-flow lanes\" and the size of the corner radius—impact pedestrian safety and the walkability of a city block?"
]

    # Start Ollama server
    ollama_process = start_ollama()

    try:
        ID_session = input("Enter session ID (or press Enter to skip): ").strip()
        if ID_session:
            os.makedirs("conversation", exist_ok=True)
            if not os.path.exists("conversation/" + ID_session + ".txt"):
                open("conversation/" + ID_session + ".txt", "w").close()

        for prompt in prompts:
            print(f"\nUser Prompt: {prompt}")
            with open("conversation/" + ID_session + ".txt", "a", encoding="utf-8") as f:
                f.write(f"User: {prompt}\n")

            for index in range(len(MODELS)):
                model = MODELS[index]
                stream_model_response(model, prompt, ID_session, index+1)

            upadte_script(prompt)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        # Stop Ollama when done
        stop_ollama(ollama_process)


if __name__ == "__main__":
    main()
