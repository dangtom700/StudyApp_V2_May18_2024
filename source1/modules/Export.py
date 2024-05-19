import modules.DataProcess as DataProcess
import modules.path as path
from csv import reader
from warnings import filterwarnings
import json
import colorama

def AnnounceFinish() -> None:
    colorama.init()
    print(colorama.Fore.GREEN + "Process executed successfully finished." + colorama.Style.RESET_ALL)

def mirrorFile_to_destination(source: str, destination: str) -> None:
    with open(source, 'r') as read_obj, open(destination, 'w') as write_obj:
        for line in read_obj:
            write_obj.write(line)

def exportTagSet(folderPath: str, banned_words: set[str]) -> None:
    """
    Export the tag set to a file in the specified folder path.

    Parameters:
        folderPath (str): The path to the folder where the tag set will be exported.
        banned_words (set[str]): A set of words to be excluded from the tag set.

    Returns:
        None

    This function retrieves the tuned word list from the specified folder path using the
    `get_tuned_word_list_from_folder` function from the `DataProcess` module. It then breaks
    the word set into a displayable format using the `break_tag_set_to_list` function from the
    `DataProcess` module. The function writes the tag set to a file specified by the
    `TagCatalog_path` constant from the `path` module. The file is opened in write mode and
    the total number of tags is written as a header. For each character in the displayable
    tag set, the function writes the character and the number of tags associated with it.
    If there are no tags for a character, a message indicating that there are no tags in
    that category is written. The function then writes each tag associated with the character.
    Finally, the function calls the `mirrorFile_to_destination` function to mirror the tag
    catalog file to the Obsidian tag catalog path.

    Note: The `DataProcess` module and the `path` module must be imported for this function
    to work properly.
    """
    word_set = sorted(DataProcess.get_tuned_word_list_from_folder(folderPath, banned_words))
    tag_set_display = DataProcess.break_tag_set_to_list(word_set)
    CHARACTER = tag_set_display.keys()

    with open(path.TagCatalog_path, "w") as outputFile:
        outputFile.write("\n# Tags (Total: " + str(len(word_set)) + ")\n")
        for char in CHARACTER:
            outputFile.write(f"\n## {char.upper()} ({len(tag_set_display[char])})\n\n")
            if tag_set_display[char] == []:
                outputFile.write("There is no tag in this category.")
            for tag in tag_set_display[char]:
                outputFile.write(f"#{tag} ")
            outputFile.write("\n")
    mirrorFile_to_destination(path.TagCatalog_path, path.Obsidian_TagCatalog_path)

def exportPDF_info(folderPath: str, banned_words: set[str]) -> None:
    """
    A function to export information about PDF files based on the input folder path and banned words.
    This function retrieves PDF filenames, processes various data about the PDFs, and writes the information to a file.
    
    Parameters:
        folderPath (str): The path to the folder containing the PDF files.
        banned_words (set[str]): A set of words to be excluded during the information extraction process.
    
    Returns:
        None
    """
    filename_list = DataProcess.get_pdf_name(folderPath)

    with open(path.PDF_info_path, "w") as outputFile:
        outputFile.write("Title;Title Length (char);Title Length (word);Multi-Tags;Tag Number;File Size (Kb);Updated Time\n")
        for filename in filename_list:
            outputFile.write(f"{filename};")
            outputFile.write(f"{len(filename)};")
            outputFile.write(f"{len(filename.strip().split())};")
            word_list = DataProcess.get_word_list_from_file(filename, banned_words)
            for word in word_list:
                outputFile.write(f"#{word}")
                if word != word_list[-1]:
                    outputFile.write(" ")
            outputFile.write(f";{len(word_list)};")
            outputFile.write(f"{DataProcess.get_file_size(folderPath + '/' + filename + ".pdf")};")
            outputFile.write(f"{DataProcess.get_updated_time(folderPath + '/' + filename + ".pdf")}\n")

def exportPDF_index(folderPath: str) -> None:
    """
    A function to export the PDF index to two separate files: PDF_index_path and Obsidian_PDF_index_path. 
    The PDF index contains a list of filenames along with their corresponding indices. 
    The function retrieves the list of PDF filenames using DataProcess.get_pdf_name() and writes the index for each filename to the specified paths. 
    The Obsidian export includes a link to each PDF file in the format [[BOOKS/{filename}.pdf|{filename}]].
    Parameters:
        folderPath (str): The path to the folder containing the PDF files.
    Returns:
        None
    """
    filename_list = DataProcess.get_pdf_name(folderPath)
    banned_words = DataProcess.get_banned_words(path.ban_path)

    with open(path.Obsidian_PDF_index_path, "w") as outputFile:
        outputFile.write("\n# PDF index (Total: " + str(len(filename_list)) + ")\n\n")
        for index, filename in enumerate(filename_list, start= 1):
            outputFile.write(f"{index}. [[BOOKS/{filename}.pdf|{filename}]]\n")

            outputFile.write("\nKeywords: ")
            keyword_list = DataProcess.get_word_list_from_file(filename, banned_words)
            
            for keyword in keyword_list:
                outputFile.write(f"#{keyword}")
                if keyword != keyword_list[-1]:
                    outputFile.write(" ")
            outputFile.write("\n\n")
    mirrorFile_to_destination(path.Obsidian_PDF_index_path, path.PDF_index_path)

def updateStat(PDF_info_file: str) -> None:
    """
    Updates the statistics of PDFs based on the information provided in the given CSV file.

    Parameters:
        PDF_info_file (str): The path to the CSV file containing the information about the PDFs.
            The CSV file should have the following format:
            - Title;Title Length (char);Title Length (word);Multi-Tags;Tag Number;Pages;File Size (byte);Updated Time

    Returns:
        None

    This function reads the CSV file and extracts the necessary data. It then analyzes the characteristics of various properties
    such as title length (char) and title length (word), tag number, pages, and file size using the `DataProcess.analyze_characteristic_of_property` function.
    The analyzed properties are stored in separate dictionaries.

    The function also retrieves the timestamp history using the `DataProcess.get_ordered_timestamps` function.

    The analyzed properties and timestamp history are used to generate a markdown table that provides statistics about the PDFs.
    The table is written to the file specified by `path.TableStat_path`.

    The function also mirrors the generated table to the destination specified by `path.Obsidian_TableStat_path`.

    Finally, the analyzed properties are converted to JSON format and written to the file specified by `path.PropertyStat_tokens_path`.
    """

    # CSV format:Title;Title Length (char);Title Length (word);Multi-Tags;Tag Number;Pages;File Size (byte);Updated Time

    with open(PDF_info_file, "r") as csv_file:
        csvreader = reader(csv_file, delimiter = ';')
        data = list(zip(*csvreader))

    title, title_length_char, title_length_word,multi_tag, tag_number, file_size, updated_time = data

    title_length_char_property = DataProcess.analyze_characteristic_of_property(title_length_char)
    title_length_word_property = DataProcess.analyze_characteristic_of_property(title_length_word)
    tag_number_property = DataProcess.analyze_characteristic_of_property(tag_number)
    file_size_property = DataProcess.analyze_characteristic_of_property(file_size)

    timestamp_history = DataProcess.get_ordered_timestamps(updated_time)
    keys = list(title_length_char_property.keys())

    with open(path.TableStat_path, "w") as outputFile:
        outputFile.write("# Statistic of PDFs\n")
        outputFile.write("\n## Title Stat\n\n")
        outputFile.write("| Characteristic| Title Length (char)| Title Length (word)|\n")
        outputFile.write("| --- | --- | --- |\n")
        for key in keys[1:]:
            outputFile.write(f"| {key} | {title_length_char_property[key]} | {title_length_word_property[key]} |\n")
        outputFile.write("\n## Keywords Stat\n\n")
        outputFile.write("| Characteristic| Tag Number | File Size (Kb)|\n")
        outputFile.write("| --- | --- | --- | --- |\n")
        for key in keys[1:]:
            outputFile.write(f"| {key} | {tag_number_property[key]} | {file_size_property[key]} |\n")
        outputFile.write("\n")

        outputFile.write("## Time Stamp History\n\n")
        counter = 0
        for timestamp in timestamp_history:
            if timestamp == timestamp_history[0]:
                outputFile.write(f"Start at {timestamp}\n")
                continue
            if timestamp == timestamp_history[-1]:
                outputFile.write(f"Most Recent at {timestamp}\n")
                continue
            if timestamp == timestamp_history[-2]:
                counter = 2
            outputFile.write(f"=> {timestamp}")
            counter += 1
            if counter < 3:
                outputFile.write(" ")
            else:
                outputFile.write("\n")
                counter = 0
    with open("F:/project/StudyLogDB/KeywordRanker/data/multi_tag.txt", "w") as outputFile:
        for tag in multi_tag:
            outputFile.write(f"{tag}\n")

    with open("F:/project/StudyLogDB/KeywordRanker/data/filename.txt", "w") as outputFile:
        for filename in title:
            outputFile.write(f"{filename}\n")
            

    mirrorFile_to_destination(path.TableStat_path, path.Obsidian_TableStat_path)

    with open(path.PropertyStat_tokens_path, "w") as outputFile:
        dict_list = [title_length_char_property, title_length_word_property, tag_number_property, file_size_property]
        json_string = json.dumps(dict_list,indent=4)
        outputFile.write(json_string)

def exportPDF_tokens(pdf_info_file: str) -> None:
    """Export PDF tokens from a given PDF info file."""
    with open(pdf_info_file, "r") as csv_file:
        reader_ = reader(csv_file, delimiter=";")
        data = list(zip(*reader_))

    PDF_token_list = [
        {
            "Title": title,
            "Title Length (char)": title_length_char,
            "Title Length (word)": title_length_word,
            "Multi-Tags": multi_tags,
            "Tag Number": tag_number,
            "File Size (Kb)": file_size,
            "Updated Time": updated_time
        } 
        for title, title_length_char, title_length_word, multi_tags, tag_number, file_size, updated_time 
        in zip(data[0], data[1], data[2], data[3], data[4], data[5], data[6])
    ]

    with open(path.PDF_tokens_path, "w") as output_file:
        json.dump(PDF_token_list, output_file, indent=4,)

def pick_number_random_book_to_read() -> None:
    filename_list = DataProcess.get_pdf_name(path.BOOKS_folder_path)
    pick_random_item = DataProcess.pick_random_number_items(filename_list, 3)
    with open(path.Obsidian_taskList_path, "a") as outputFile:
        outputFile.write("\n\n" + DataProcess.get_current_time() + "\n\n")
        for filename in pick_random_item:
            outputFile.write(f"- [ ] Read a chapter of [[BOOKS/{filename}.pdf|{filename}]]")
            if filename != pick_random_item[-1]:
                outputFile.write("\n")
    mirrorFile_to_destination(path.Obsidian_taskList_path, path.taskList_path)

def rewrite_ban_file(banned_word: set[str]) -> None:
    with open(path.ban_path, "w") as outputFile:
        for word in banned_word:
            outputFile.write(word + "\n")

def search_file(input: str) -> None:
    colorama.init()
    print(colorama.Fore.MAGENTA + "Search Result" + colorama.Style.RESET_ALL)
    filename_list = DataProcess.get_pdf_name(path.BOOKS_folder_path)
    for filename in filename_list:
        if input in filename:
            print(colorama.Fore.GREEN + filename + colorama.Style.RESET_ALL)