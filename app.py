from src.app.main import main
import flet as ft
import logging
import traceback
import sys

logger = logging.getLogger(__name__)

def main_wrapper(page):
    """Wrapper around main to catch and log all exceptions."""
    try:
        logger.info("Initializing main page...")
        return main(page)
    except Exception as e:
        logger.error(f"CRITICAL: Uncaught exception in main: {e}")
        logger.error(traceback.format_exc())
        # Try to show error on page if possible
        try:
            import flet as ft
            page.snack_bar = ft.SnackBar(ft.Text(f"CRITICAL ERROR: {str(e)}", color=ft.Colors.RED_400))
            page.snack_bar.open = True
            page.update()
        except:
            pass
        raise

if __name__ == "__main__":
    try:
        ft.run(main_wrapper)
    except Exception as e:
        logger.critical(f"FATAL: Application crashed: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)
