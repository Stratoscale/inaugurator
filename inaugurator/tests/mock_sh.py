

class mock_sh():
    """
    mock_sh is a class to mock sh.run commands and validate the commands are exactly as expected
    """
    def __init__(self):
        """
        create mock_sh instance
        """
        self.expectedCommands = []

    def setCommands(self, expctedCommands):
        """
        set extepected commands for mock_sh instance
        @param expctedCommands: all the expected commands and the result for each one
        @type expctedCommands: list of dict with 'command' and 'result'
         [{"command": "<cmd>", "result": "<result>"}]
        @return:None
        @rtype: None
        """
        self.expectedCommands = expctedCommands

    def runShell(self, command):
        """
        mock a shell command, if command not found in expected, raised exception
        if command exist in expected command, returns the result
        @param command: shell command to execute
        @type command: string
        @return: result of command from expected commands list
        @rtype: type in expected commands
        """
        foundList = [x for x in self.expectedCommands if x["command"] == command]
        if len(foundList) == 0:
            msg = "Command '%s' is not in expected commands." % command
            if self.expectedCommands:
                msg += " Expected Command: %s" % (self.expectedCommands)
            raise Exception(msg)
        found = foundList[0]
        self.expectedCommands.remove(found)
        result = found["result"]
        if callable(result):
            output = result()
        elif isinstance(result, Exception):
            raise result
        else:
            print "Expected command run: ", found, " result: ", result
            output = result
        return output
