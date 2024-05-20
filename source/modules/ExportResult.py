import colorama
import modules.WordFilter as wf
import logging
import modules.path as path

wf.setup_logging(path.application_log)

def AnnounceFinished(command: str) -> None:
    colorama.init()
    print(colorama.Fore.GREEN + "Command executed successfully!" + colorama.Style.RESET_ALL)
    logging.info(f"Command {command} executed successfully!")
    colorama.deinit()