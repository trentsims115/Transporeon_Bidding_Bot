import logging
from logging.handlers import TimedRotatingFileHandler

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, *args, **kwargs):
        filename += '.log'
        super().__init__(filename, *args, **kwargs)

    def getLogFileName(self, times):
        default_log_file = super().getLogFileName(times)
        log_file_name = default_log_file[:-4] + times.strftime("-%Y-%m-%d") + ".log"
        return log_file_name

class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO

def create_logger():
    """Creates and sets up the logger"""
    from Utilities import storage

# Create a logger
logger = logging.getLogger('BotLogger')
logger.setLevel(logging.DEBUG) # Set to the lowest level you want to log

# Create a handler for INFO logs
info_handler = CustomTimedRotatingFileHandler(f'C:/Bots/logs/Info/transporeon_info_log_file', when="midnight", interval=1)
info_handler.setLevel(logging.INFO)
info_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - %(pathname)s - %(lineno)d')
info_handler.setFormatter(info_formatter)
info_handler.addFilter(InfoFilter())
logger.addHandler(info_handler)

# Create a handler for ERROR logs
error_handler = CustomTimedRotatingFileHandler(f'C:/Bots/logs/Errors/transporeon_error_log_file', when="midnight", interval=1)
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - %(pathname)s - %(lineno)d')
error_handler.setFormatter(error_formatter)
logger.addHandler(error_handler)
