import colorama
import argparse

def app():

    parser = argparse.ArgumentParser(prog="Study Logging and Database",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    
    parser.add_argument("--exportTagSet", action= 'store_true', help="Export a tag set to a file named 'tags.md' in the specified folder path")
    parser.add_argument("--exportPDF_info", action= 'store_true', help="Export a CSV file with the size and tags of the files in the specified folder path")
    parser.add_argument("--exportPDF_index", action= 'store_true', help="Export a list of PDF file in a given directory in .md format")
    parser.add_argument("--updateStat", action= 'store_true', help="Update the statistics of PDF files")
    parser.add_argument("--exportPDF_tokens", action= 'store_true', help="Export a CSV file with the tokens of the files in the specified folder path")
    parser.add_argument("--updateData", action= 'store_true', help="Update all statistics of PDF files")
    parser.add_argument("--getTaskList", action= 'store_true', help="Export a list of tasks in .md format")
    parser.add_argument("--searchFile", type=str, help="Search for files in the specified folder path")

    args = parser.parse_args()

    if args.exportTagSet:
        pass

    if args.exportPDF_info:
        pass

    if args.exportPDF_index:
        pass

    if args.updateStat:
        pass

    if args.exportPDF_tokens:
        pass

    if args.updateData:
        pass

    if args.getTaskList:
        pass

    if args.searchFile:
        pass


if __name__ == "__main__":
    app()