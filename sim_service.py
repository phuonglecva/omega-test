from fastapi import FastAPI
import pyarrow.parquet as pq
import os
app = FastAPI()

class YoutubeIdManger:
    def __init__(self) -> None:
        self.ids = set()
        if not os.path.exists("youtube_ids.parquet"):
            self.download_ids()
        self.load_ids()
    
    def load_ids(self):
        filename = "youtube_ids.parquet"
        table = pq.read_table(filename)
        df = table.to_pandas()
        self.ids = df['youtube_id'].tolist()
        self.ids = set(self.ids)
    
    def download_ids(self):
        """
        wget https://huggingface.co/datasets/jondurbin/omega-multimodal-ids/resolve/main/youtube_ids.parquet
        """
        import os
        if os.path.exists("youtube_ids.parquet"):        
            os.remove("youtube_ids.parquet")
        print("Downloading youtube_ids.parquet")
        os.system("wget https://huggingface.co/datasets/jondurbin/omega-multimodal-ids/resolve/main/youtube_ids.parquet")
        print("Downloaded youtube_ids.parquet")        
    
    def reload(self):
        self.download_ids()
        self.load_ids()
        
    def check_exists(self, yt_id):
        return yt_id in self.ids

    def filter_ids(self, yt_ids):
        return [yt_id for yt_id in yt_ids if yt_id in self.ids]
    
@app.get("/")
def read_root():
    return {"Hello": "World"}

from pydantic import BaseModel
class YoutubeIdsRequest(BaseModel):
    ids: list[str]

manager = YoutubeIdManger()

# each 15 min auto reload the ids
import threading
def reload_ids():
    import time
    print("Starting reload_ids")
    while True:
        time.sleep(60 * 15)
        manager.reload()

reload_thread = threading.Thread(target=reload_ids)
reload_thread.start()

@app.post("/api/v1/unique")
def check_unique(yt_ids: YoutubeIdsRequest):
    yt_ids = yt_ids.ids
    try:
        filtered_ids = manager.filter_ids(yt_ids)
        return {
            "unique_ids": filtered_ids
        }
    except Exception as e:
        return {
            "error": str(e),
            "unique_ids": yt_ids
        }

@app.get("/api/v1/exists/{yt_id}")
def check_unique(yt_id: str):
    try:
        return {
            "exists": manager.check_exists(yt_id)
        }
    except Exception as e:
        return {
            "error": str(e),
            "exists": False
        }