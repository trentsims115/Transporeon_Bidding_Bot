import time
import sys
import shutil
import msvcrt  # Windows-only

# ANSI color codes
COLOR_CYAN = "\x1b[96m"
COLOR_GREEN = "\x1b[92m"
COLOR_RESET = "\x1b[0m"

def _erase_line():
    width = shutil.get_terminal_size((80, 20)).columns
    sys.stdout.write("\r" + " " * (width - 1) + "\r")
    sys.stdout.flush()

def countdown(seconds: int, message: str = "Continuing in {remaining}s… Press Enter to skip."):
    """
    Shows a colored countdown with spinner + progress bar.
    User can press Enter to skip early. (Windows-only due to msvcrt)
    """
    if seconds <= 0:
        return

    spinner_chars = "|/-\\"
    spinner_index = 0
    bar_width = 30
    total = seconds

    # Hide cursor
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()

    try:
        for remaining in range(seconds, 0, -1):
            # Compute progress [#####.....]
            done = total - remaining
            filled = int(bar_width * done / total)
            bar = COLOR_GREEN + "[" + "#" * filled + "." * (bar_width - filled) + "]" + COLOR_RESET

            # Static part of message (no spinner yet)
            text = message.format(remaining=remaining)

            # Inner loop: up to 1 second, but update spinner + check Enter
            start = time.time()
            while time.time() - start < 1:
                # Check for Enter key (skip)
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\r", "\n"):
                        _erase_line()
                        return

                # Spinner frame
                spinner = spinner_chars[spinner_index % len(spinner_chars)]
                spinner_index += 1

                line = f"\r{COLOR_CYAN}{spinner} {bar} {text}{COLOR_RESET}"
                sys.stdout.write(line)
                sys.stdout.flush()

                time.sleep(0.1)  # smooth spinner

        # Finished normally
        _erase_line()

    finally:
        # Restore cursor
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()
