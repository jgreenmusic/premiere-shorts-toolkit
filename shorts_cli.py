"""Console entry point of the installed app (shorts-cli.exe). The app window runs its
background jobs through this; you can also use it in a terminal exactly like shorts.py."""
import runtime

runtime.setup()

import shorts  # noqa: E402

if __name__ == "__main__":
    shorts.main()
