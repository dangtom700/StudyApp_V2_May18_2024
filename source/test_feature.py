""" Note Review System and Tailored keyword Suggestion
The goal of this feature is to trigger the creativity of note taking and liking
information between any two or different subjects or topics. Through this 
activity, it encourages more creativity with the content of the note and create
helpful keywords for fast retrieval.

The structure of this feature is as follows:

- The program will randomly choose 3 notes from the note list database
- The program will then export the results into a dedicated Markdown file with 
the following format:

[date]
- [Note Title 1]
- [Note Title 2]
- [Note Title 3]
Keyword: [Keyword 1], [Keyword 2], [Keyword 3], ...

- In another file in the Review folder, the program will export the result in
the following format:

Title for file name : MM-DD-YYYY

# [Date]

## Primary Notes
(Main notes for today's reading)
- [Note 1]
- [Note 2]
- [Note 3]

Keywords: [Keyword 1], [Keyword 2], [Keyword 3], ...

## Additional Sources
(Any files or websites that are useful for today's reading)
-


## Review
(Anything interesting details that needs to be reviewed)
- 

## Explore
(Expand beyond the notes' topic)
-

## Summary
(What is learnt from today's reading)
-

## Plan
(How to use new information for future purposes)
-

Note: The hope for this feature is that at least written notes are at least 
revisited once. From reading those notes, if there is something interesting pop
up, grap it and explore that idea and find out a suitable keyword for it.
"""

import sqlite3

def randomizeNoteList():
    conn = sqlite3.connect('data\\chunks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT note_name FROM note_list ORDER BY RANDOM() LIMIT 3")
    result = cursor.fetchall()
    conn.close()
    # clear up the string in the list
    # example: [('Note 1',), ('Note 2',), ('Note 3',)]
    # to: ['Note 1', 'Note 2', 'Note 3']
    result = [note[0] for note in result]
    result = [f"[[StudyNotes/{note}.md|{note}.md]]" for note in result]
    print(f"Note list randomized: {result}")
    return result

def exportNoteReviewTask(note_list: list) -> None:
    with open ("data\\Task List.md", 'a', encoding='utf-8') as f:
        for note in note_list:
            f.write(f"- {note}\n")
    print("Note review task exported.")

def exportStudyLogTemplate(note_list: list) -> None:
    with open ("D:\\project\\StudyLog\\template\\(template) Study Log.md", 'rb') as f:
        # get al content from template
        content = f.read()

    from datetime import datetime
    date = datetime.now().strftime("%a, %b %d, %Y, %H_%M_%S")
    with open (f"sample\\{date}.md", 'w', encoding='utf-8') as f:
        change_date = content.decode('utf-8').replace("Date: {date}", f"Date: {date}")
        change_note = change_date.replace("- {note1}\n- {note2}\n- {note3}", f"- {note_list[0]}\n- {note_list[1]}\n- {note_list[2]}")

        f.write(change_note)

    print("Modified study log template exported to 'Review' folder.")

def getNoteReviewTask() -> None:
    note_list = randomizeNoteList()
    exportNoteReviewTask(note_list)
    exportStudyLogTemplate(note_list)