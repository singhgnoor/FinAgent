"""The entry point of the project."""

from core.log import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    """Example entry point showing logging initialization."""
    # Initialize logging FIRST, before anything else
    setup_logging(run_id="example_run")
    
    logger.info("[main] FinAgent pipeline starting")
    
    # Your pipeline code here
    # from core.graph import run_once
    # from core.state import RawSignal, SignalType
    # ...
    
    logger.info("[main] FinAgent pipeline complete")


if __name__ == "__main__":
    main()

