def retrieve_raw_data(option: str) -> None:
    path_option = {"filename":"F:/project/StudyLogDB/mini_project/KeywordRanker/data/filename.txt",
                   "Tag":"F:/project/StudyLogDB/mini_project/KeywordRanker/data/multi_tag.txt",}
    with open(path_option[option]) as f:
        lines = f.readlines()
    return lines[1:]

def export_tag_list(Tag_set: set[str]) -> None:
    with open("F:/project/StudyLogDB/mini_project/KeywordRanker/data/Tag.txt", 'w') as f:
    	for tag in sorted(Tag_set):
        	f.write(tag + '\n')

def export_trash_tags(tags_set: set[str]):
    trash_tags = []

    for tag in tags_set:
        # Criteria 1: Single-letter tags
        if len(tag) == 1:
            trash_tags.append(tag)
        # Criteria 2: Very short tags
        elif len(tag) <= 3:
            trash_tags.append(tag)
        # Criteria 3: Tags with special characters or symbols
        elif not tag.isalnum():
            trash_tags.append(tag)
        # Criteria 4: Repetitive or nonsensical tags
        elif tag.count('_') >= 2:  # Checking if tag has more than one underscore
            trash_tags.append(tag)

    print("Trash tags:", len(trash_tags))
    print("Tag Set after filter:", len(tags_set) - len(trash_tags))
    with open("F:/project/StudyLogDB/mini_project/KeywordRanker/data/ban.txt", 'w') as f:
        for tag in sorted(trash_tags):
            f.write(tag + '\n')

def export_tag_list(Tag_set: set[str]) -> None:
    # create a word length and word dictionary
    word_length_word_list_dict: dict[int, list[str]] = {}
    for tag in Tag_set:
        word_length = len(tag)
        word_length_word_list_dict.setdefault(word_length, []).append(tag)

    with open("F:/project/StudyLogDB/mini_project/KeywordRanker/data/tag.md", 'w') as f:
        f.write("# Tags\n")
        for key, value in word_length_word_list_dict.items():
            f.write("\n" + ' '.join(value) + '\n')

def process_raw_tags(lines: list[str]) -> None:
    Tag_set = set()
    for line in lines:
        tag_line = set(line.split())
        tag_line = set(map(lambda x: x.removeprefix('#'), tag_line))
        Tag_set = Tag_set.union(tag_line)
    print("Tag_set:", len(Tag_set))
    return(Tag_set)

def process_filename_to_single_tags(lines: list[str]) -> None:
    Tag_set = set()
    for line in lines:
        tag = set(line.strip().split())
        Tag_set = Tag_set.union(tag)
    print("Tag_set:", len(Tag_set))
    return(Tag_set)

if __name__ == "__main__":
    tag_lines = retrieve_raw_data("Tag")
    Tag_set = process_raw_tags(tag_lines)
    print("Tag_set:", len(Tag_set))

    export_trash_tags(Tag_set)
    export_tag_list(Tag_set)
    