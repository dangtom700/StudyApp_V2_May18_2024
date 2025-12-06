from subprocess import run
from os import listdir
from json import dump

# ------------------------------------------------------------
# Run external application and read its output
# ------------------------------------------------------------
def run_app():
    run(["config\\main"], shell=True)
    with open("outputPrompt.txt", "r", encoding="utf-8") as f:
        output = f.readlines()
    return output[2:]  # Skip first two lines


# ------------------------------------------------------------
# Extract structured items and group them by ID
# ------------------------------------------------------------
def extract_items(output_lines: list[str], topic: str):
    items = {}  # key = ID
    current_item = {}

    for line in output_lines:
        line = line.strip()

        if line.startswith("ID:"):
            # If we already collected an item, store it before starting a new one
            if current_item:
                store_item(items, current_item, topic)

            current_item = {"ID": line.split("ID:")[1].strip()}

        elif line.startswith("Distance:"):
            current_item["Distance"] = line.split("Distance:")[1].strip()

        elif line.startswith("Name:"):
            current_item["Name"] = line.split("Name:")[1].strip().strip("[]")

    # Store final item
    if current_item:
        store_item(items, current_item, topic)

    return items


# ------------------------------------------------------------
# Add extracted item into dictionary-of-items (merge if exists)
# ------------------------------------------------------------
def store_item(all_items: dict, item: dict, topic: str):
    item_id = item["ID"]

    if item_id not in all_items:
        all_items[item_id] = {
            "ID": item_id,
            "Name": item.get("Name", ""),
            "Distance": {}
        }

    # Add topic-distance mapping
    all_items[item_id]["Distance"][topic] = item.get("Distance", None)


# ------------------------------------------------------------
# Write 50 repetitions of topic + conversation into PROMPT.txt
# ------------------------------------------------------------
def write_prompt(topic_path: str, topic_name: str):
    with open("PROMPT.txt", "a", encoding="utf-8") as pf:
        # Repeat topic 50 times
        for _ in range(50):
            pf.write(f"{topic_name} ")
        pf.write("\n")

        # Append conversation text
        with open(topic_path, "r", encoding="utf-8") as f:
            pf.writelines(f.readlines())
            pf.write("\n\n")

def edit_config_file():
    """ Run this function once to edit config/main.bat with the required settings.
    set "showComponents=0"
    set "extractText=0"
    set "updateDatabaseInformation=0"
    set "processWordFreq=0"
    set "computeTFIDF=0"
    set "computeRelationalDistance=0"
    set "ideation=0"
    set "promptReference=1"
    """
    with open("config/main.bat", "r", encoding="utf-8") as bf:
        lines = bf.readlines()
    with open("config/main.bat", "w", encoding="utf-8") as bf:
        for line in lines:
            if line.startswith('set "showComponents='):
                bf.write('set "showComponents=0"\n')
            elif line.startswith('set "extractText='):
                bf.write('set "extractText=0"\n')
            elif line.startswith('set "updateDatabaseInformation='):
                bf.write('set "updateDatabaseInformation=0"\n')
            elif line.startswith('set "processWordFreq='):
                bf.write('set "processWordFreq=0"\n')
            elif line.startswith('set "computeTFIDF='):
                bf.write('set "computeTFIDF=0"\n')
            elif line.startswith('set "computeRelationalDistance='):
                bf.write('set "computeRelationalDistance=0"\n')
            elif line.startswith('set "ideation='):
                bf.write('set "ideation=0"\n')
            elif line.startswith('set "promptReference='):
                bf.write('set "promptReference=1"\n')
            else:
                bf.write(line)

# ------------------------------------------------------------
# MAIN PROCESS
# ------------------------------------------------------------
if __name__ == "__main__":
    merged = {}  # Final dictionary of all items by ID
    edit_config_file()

    # 1. Process each topic individually
    topics = [t for t in listdir("conversation") if t.endswith(".txt")]
    sub_topics = topics.copy()

    for topic_file in topics:
        for second_topic in sub_topics:
            if topic_file == second_topic:
                topic_name = topic_file.removesuffix(".txt").replace("_", " ")
            else:
                topic_name = f"{topic_file.removesuffix('.txt').replace('_', ' ')} and {second_topic.removesuffix('.txt').replace('_', ' ')}"

            # Clear PROMPT.txt
            open("PROMPT.txt", "w").close()

            # Write input prompt for this topic
            write_prompt(f"conversation/{topic_file}", topic_name)
            if topic_file != second_topic:
                write_prompt(f"conversation/{second_topic}", topic_name)

            # Run model
            output_lines = run_app()

            # Extract & merge
            topic_items = extract_items(output_lines, topic_name)

            for item_id, item in topic_items.items():
                if item_id not in merged:
                    merged[item_id] = item
                else:
                    merged[item_id]["Distance"].update(item["Distance"])
        sub_topics.remove(topic_file)

    # 2. Process GENERAL run using ALL files
    open("PROMPT.txt", "w").close()

    for topic_file in topics:
        name = topic_file.removesuffix(".txt").replace("_", " ")
        write_prompt(f"conversation/{topic_file}", name)

    # Run model
    output_lines = run_app()

    # Extract & merge
    general_items = extract_items(output_lines, "general")

    for item_id, item in general_items.items():
        if item_id not in merged:
            merged[item_id] = item
        else:
            merged[item_id]["Distance"].update(item["Distance"])

    # --------------------------------------------------------
    # Save final JSON (list of items)
    # --------------------------------------------------------
    with open("data/recommendations.json", "w", encoding="utf-8") as jf:
        dump(list(merged.values()), jf, indent=4, ensure_ascii=False)
