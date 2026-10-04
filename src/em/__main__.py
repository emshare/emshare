"""支持 ``python3 -m em`` 调用。"""

import sys

from em.cli import main

if __name__ == "__main__":
    sys.exit(main())
