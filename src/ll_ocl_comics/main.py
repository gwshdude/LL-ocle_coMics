
from app import MokuroTranslator
import logging

logger = logging.getLogger(__name__)

def main():
    logger.setLevel(logging.DEBUG)
    app = MokuroTranslator()
    app.mainloop()

if __name__ == "__main__":
    main()
