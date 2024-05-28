import argparse
import modules.updateData as updateData
import modules.Export as Export
import modules.path as path


def app():

    parser = argparse.ArgumentParser(prog="Study Logging and Database",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    
    parser.add_argument("--updateData", action= 'store_true', help="Update all statistics of PDF files")
    parser.add_argument("--getTaskList", action= 'store_true', help="Export a list of tasks in .md format")
    parser.add_argument("--searchFileInDatabase", type=str, help="Search for files in the specified folder path")

    args = parser.parse_args()

    if args.updateData:
        updateData.log_message(f"Updating all data of PDF files...")
        updateData.update_data()
        updateData.log_message(f"Finished updating all data of PDF files.")

    if args.getTaskList:
        updateData.log_message(f"Exporting task list to 'Task List.md' in {path.Obsidian_taskList_path}...")
        Export.getTaskList(path.taskList_path, path.Obsidian_taskList_path)
        updateData.log_message(f"Finished exporting task list to 'Task List.md' in {path.Obsidian_taskList_path}.")

    if args.searchFileInDatabase:
        updateData.log_message(f"Searching for keyword '{args.searchFileInDatabase}'...")
        updateData.log_message(f"Searching for files in database...")
        Export.searchFileInDatabase(args.searchFileInDatabase)
        updateData.log_message(f"Finished searching for keyword '{args.searchFileInDatabase}'.")

if __name__ == "__main__":
    app()