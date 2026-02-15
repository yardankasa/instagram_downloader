from json import load
import instaloader
import os
from dotenv import load_dotenv

load_dotenv()

loader = instaloader.Instaloader()

loader.login(os.getenv("test_username"), os.getenv("test_password"))

save_session_to_file(loader.context, "session.json")


# post ( reels and other posts ) downloader section

post_downloader = loader.download_post()
