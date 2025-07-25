
from app import MokuroTranslator
import logging
import sys
import traceback

def main():
    # Configure logging to show debug output in terminal
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set root logger level
    logging.getLogger().setLevel(logging.INFO)
    
    print("Starting Mokuro Translator with debug logging enabled...")
    print("All translation requests and responses will be logged to this terminal.")
    print("=" * 60)
    
    try:
        # Create and run the app - let GUI initialization errors propagate
        app = MokuroTranslator()
        print("GUI initialized successfully. Starting main loop...")
        app.mainloop()
        print("Application closed normally.")
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user (Ctrl+C)")
        
    except Exception as e:
        print(f"\nERROR: Application crashed during runtime: {e}")
        print("Full traceback:")
        traceback.print_exc()
        print("\nPress Enter to exit...")
        try:
            input()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
