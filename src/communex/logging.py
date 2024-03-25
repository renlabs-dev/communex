import sys
from loguru import logger


logger.level("INFO")

logger.opt(colors=True).add(sys.stderr, format="<level>{message}</level>")
logger.opt(colors=True).add(sys.stdout, format="<level>{message}</level>")
logger.opt(colors=True).add("communex.log", format="<level>{message}</level>")

def get_logger():
    return logger