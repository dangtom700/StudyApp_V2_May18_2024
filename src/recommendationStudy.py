from subprocess import run
from os import listdir
from os.path import join
from json import dump, load
from modules.path import source_data
from random import shuffle

def run_app():
    run(["config\\main"], shell=True)
    with open("outputPrompt.txt", "r", encoding="utf-8") as f:
        output = f.readlines()
    return output[2:]  # Skip first two lines

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

def disable_compiler():
    with open("config/main.bat", "r", encoding="utf-8") as bf:
        lines = bf.readlines()
    with open("config/main.bat", "w", encoding="utf-8") as bf:
        for line in lines:
            if line.strip().startswith("g++ src/main.cpp"):
                bf.write("@REM " + line)
            else:
                bf.write(line)

def enable_compiler():
    with open("config/main.bat", "r", encoding="utf-8") as bf:
        lines = bf.readlines()
    with open("config/main.bat", "w", encoding="utf-8") as bf:
        for line in lines:
            if line.strip().startswith("@REM g++ src/main.cpp"):
                bf.write(line.replace("@REM ", ""))
            else:
                bf.write(line)

def warm_up_app():
    # Warm up run to avoid initial overhead
    with open("PROMPT.txt", "w", encoding="utf-8") as pf:
        pf.write("""
        What is Lorem Ipsum?
        Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum.

        Why do we use it?
        It is a long established fact that a reader will be distracted by the readable content of a page when looking at its layout. The point of using Lorem Ipsum is that it has a more-or-less normal distribution of letters, as opposed to using 'Content here, content here', making it look like readable English. Many desktop publishing packages and web page editors now use Lorem Ipsum as their default model text, and a search for 'lorem ipsum' will uncover many web sites still in their infancy. Various versions have evolved over the years, sometimes by accident, sometimes on purpose (injected humour and the like).


        Where does it come from?
        Contrary to popular belief, Lorem Ipsum is not simply random text. It has roots in a piece of classical Latin literature from 45 BC, making it over 2000 years old. Richard McClintock, a Latin professor at Hampden-Sydney College in Virginia, looked up one of the more obscure Latin words, consectetur, from a Lorem Ipsum passage, and going through the cites of the word in classical literature, discovered the undoubtable source. Lorem Ipsum comes from sections 1.10.32 and 1.10.33 of "de Finibus Bonorum et Malorum" (The Extremes of Good and Evil) by Cicero, written in 45 BC. This book is a treatise on the theory of ethics, very popular during the Renaissance. The first line of Lorem Ipsum, "Lorem ipsum dolor sit amet..", comes from a line in section 1.10.32.

        The standard chunk of Lorem Ipsum used since the 1500s is reproduced below for those interested. Sections 1.10.32 and 1.10.33 from "de Finibus Bonorum et Malorum" by Cicero are also reproduced in their exact original form, accompanied by English versions from the 1914 translation by H. Rackham.

        Where can I get some?
        There are many variations of passages of Lorem Ipsum available, but the majority have suffered alteration in some form, by injected humour, or randomised words which don't look even slightly believable. If you are going to use a passage of Lorem Ipsum, you need to be sure there isn't anything embarrassing hidden in the middle of text. All the Lorem Ipsum generators on the Internet tend to repeat predefined chunks as necessary, making this the first true generator on the Internet. It uses a dictionary of over 200 Latin words, combined with a handful of model sentence structures, to generate Lorem Ipsum which looks reasonable. The generated Lorem Ipsum is therefore always free from repetition, injected humour, or non-characteristic words etc.
                 """)
    enable_compiler()
    run_app()

if __name__ == "__main__":
    # Load existing recommendations as dict
    loaded_list = load(open("data/recommendations.json", "r", encoding="utf-8"))
    merged = {item["ID"]: item for item in loaded_list}

    edit_config_file()
    warm_up_app()
    disable_compiler()
    existing_category = set()
    for item in merged.values():
        existing_category.update(item.get("Distance", {}).keys())

    # 1. Process each topic individually
    topics = [t for t in listdir("conversation") if t.endswith(".txt")]
    sub_topics = topics.copy()

    for topic_file in topics:
        for second_topic in sub_topics:
            if topic_file == second_topic:
                topic_name = topic_file.removesuffix(".txt").replace("_", " ")
            else:
                topic_name = f"{topic_file.removesuffix('.txt').replace('_', ' ')} and {second_topic.removesuffix('.txt').replace('_', ' ')}"
            
            if topic_name in existing_category:
                continue

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
    if "general" not in existing_category:
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

    # 3. Process any remaining individual topics
    files = listdir(source_data); shuffle(files)
    files = [
        file for file in files
        if file.endswith(".txt")
        and file.removesuffix(".txt") not in existing_category
    ]
    count = 0
    for file in files:
        # Clear PROMPT.txt
        open("PROMPT.txt", "w").close()
        topic_name = file.removesuffix(".txt")
        print(f"Processing topic ({files.index(file) + 1}/{len(files)}): {topic_name}")

        # Write input prompt for this topic
        write_prompt(join(source_data, file), topic_name)

        # Run model
        output_lines = run_app()

        # Extract & merge
        topic_items = extract_items(output_lines, topic_name)

        for item_id, item in topic_items.items():
            if item_id not in merged:
                merged[item_id] = item
            else:
                merged[item_id]["Distance"].update(item["Distance"])

        count += 1
        if count % 100 == 0:
            print("Writing final recommendations to data/recommendations.json")
            with open("data/recommendations.json", "w", encoding="utf-8") as jf:
                dump(list(merged.values()), jf, indent=4, ensure_ascii=False)
            count = 0
    
    enable_compiler()
