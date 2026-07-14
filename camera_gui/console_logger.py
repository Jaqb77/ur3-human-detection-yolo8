import sys
from datetime import datetime

class ConsoleLogger:
    """
    Custom stream wrapper that redirects console outputs (sys.stdout/sys.stderr)
    both to the terminal and to a text log file, prepending a timestamp to each line.
    """
    def __init__(self, filename="terminal_logs.txt"):
        self.terminal = sys.stdout
        self.log_file = open(filename, "a", encoding="utf-8")
        self.new_line = True

    def write(self, message):
        # 1. Print to the actual terminal
        self.terminal.write(message)
        
        # 2. Write to the file, adding the timestamp prefix to each new line
        if message:
            lines = message.split('\n')
            for i, line in enumerate(lines):
                # Prepends timestamp if starting a new line and the line has content
                if self.new_line and line:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.log_file.write(f"[{timestamp}] ")
                    self.new_line = False
                
                self.log_file.write(line)
                
                # If we split by newline, re-add the newline and mark flag for next prefix
                if i < len(lines) - 1:
                    self.log_file.write('\n')
                    self.new_line = True
                    
            self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
