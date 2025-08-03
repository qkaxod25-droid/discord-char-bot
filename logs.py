import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Initializes the logging configuration for the application."""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create a rotating file handler
    # This will create a new file when the log file reaches 5MB, keeping up to 5 old log files.
    file_handler = RotatingFileHandler(
        'logs/discord_bot.log',
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # Create a console handler
    console_handler = logging.StreamHandler()

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the root logger
    # Avoid adding handlers if they already exist (e.g., during reloads)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
