import argparse
import modules.ExportResult as er
import modules.WordFilter as wf
import logging
import modules.path as path

wf.setup_logging(path.application_log)

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
        logging.info("Exporting tag set to 'tags.md' in the specified folder path...")
        # process here
        er.AnnounceFinished("--exportTagSet")

    if args.exportPDF_info:
        logging.info("Exporting PDF info to 'PDF_info.csv' in the specified folder path...")
        # process here
        er.AnnounceFinished("--exportPDF_info")

    if args.exportPDF_index:
        logging.info("Exporting PDF index to 'PDF_index.md' in the specified folder path...")
        # process here
        er.AnnounceFinished("--exportPDF_index")

    if args.updateStat:
        logging.info("Updating statistics of PDF files...")
        # process here
        er.AnnounceFinished("--updateStat")

    if args.exportPDF_tokens:
        logging.info("Exporting PDF tokens to 'PDF_tokens.csv' in the specified folder path...")
        # process here
        er.AnnounceFinished("--exportPDF_tokens")

    if args.updateData:
        logging.info("Updating all statistics of PDF files...")
        # process here
        er.AnnounceFinished("--updateData")

    if args.getTaskList:
        logging.info("Exporting task list to 'task_list.md' in the specified folder path...")
        # process here
        er.AnnounceFinished("--getTaskList")

    if args.searchFile:
        logging.info("Searching for files in the specified folder path...")
        # process here
        er.AnnounceFinished("--searchFile")


if __name__ == "__main__":
    app()