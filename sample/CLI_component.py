class CLI_command:

    def __init__(self, command_name: str, description: str, command_line: str, inputs: list):
        self.command_name = command_name
        self.command_line = command_line
        self.description = description
        self.inputs = inputs

    def call_inputs(self):
        for input in self.inputs:
            print([input], end=" ")

if __name__ == "__main__":
    exportTagSet = CLI_command("exportTagSet", "Export a tag set to a file named 'tags.md' in the specified folder path", "exportTagSet", ["path"])
    exportTagSet.call_inputs()