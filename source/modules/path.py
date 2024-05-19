from os import getcwd

DB_name = "data\\StudyLogDB.db"

StudyApp_root_path = getcwd() + "\\"
StudyLog_root_path = "F:\\project\\StudyLog\\"

ban_path = StudyApp_root_path + "data\\ban.txt" #Used
PDF_info_path = StudyApp_root_path + "data\\PDF_info.csv" #Used
PDF_tokens_path = StudyApp_root_path + "data\\PDF_tokens.json" #Used
PropertyStat_tokens_path = StudyApp_root_path + "data\\PropertyStat_tokens.json"
taskList_path = StudyApp_root_path + "data\\TaskList.txt"
TableStat_path = StudyApp_root_path + "data\\Table Stat.txt" #Used
PDF_index_path = StudyApp_root_path + "data\\PDF index.txt" #Used
TagCatalog_path = StudyApp_root_path + "data\\Tag Catalog.txt" #Used

BOOKS_folder_path = StudyLog_root_path + "BOOKS" #Used
Obsidian_TableStat_path = StudyLog_root_path + "Dashboard\\Table Stat.md" #Used
Obsidian_PDF_index_path = StudyLog_root_path + "Dashboard\\PDF index.md" #Used
Obsidian_TagCatalog_path = StudyLog_root_path + "Dashboard\\Tag Catalog.md" #Used
Obsidian_taskList_path = StudyLog_root_path + "Task List.md" #Used