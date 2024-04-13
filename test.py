from omega.video_utils import download_video

texts = """"""
texts = [text.split(":") for text in texts.split("\n")]
PROXIES = [
    f"http://{text[2]}:{text[3]}@{text[0]}:{text[1]}"
    for text in texts
]

print(PROXIES)
import time
import random
start = time.time()
path = download_video("HtxlQVkqinc", 0, 300, random.choice(PROXIES))

print(time.time() - start)