import os
import random
import time
from typing import List, Tuple

import bittensor as bt

from omega.protocol import VideoMetadata
from omega.imagebind_wrapper import ImageBind
from omega.constants import MAX_VIDEO_LENGTH, FIVE_MINUTES
from omega import video_utils


if os.getenv("OPENAI_API_KEY"):
    from openai import OpenAI
    OPENAI_CLIENT = OpenAI()
else:
    OPENAI_CLIENT = None

with open("PROXIES.txt") as f:
    proxies = f.readlines()
PROXIES = [f"http://{proxy.strip()}" for proxy in proxies]

def get_description(yt: video_utils.YoutubeDL, video_path: str) -> str:
    """
    Get / generate the description of a video from the YouTube API.
    
    Miner TODO: Implement logic to get / generate the most relevant and information-rich
    description of a video from the YouTube API.
    """
    description = yt.title
    if yt.description:
        description += f"\n\n{yt.description}"
    return description


def get_relevant_timestamps(query: str, yt: video_utils.YoutubeDL, video_path: str) -> Tuple[int, int]:
    """
    Get the optimal start and end timestamps (in seconds) of a video for ensuring relevance
    to the query.

    Miner TODO: Implement logic to get the optimal start and end timestamps of a video for
    ensuring relevance to the query.
    """
    start_time = 0
    end_time = min(yt.length, MAX_VIDEO_LENGTH)
    return start_time, end_time

def check_unique(video_id: str):    
    import requests
    URL = f"http://localhost:8000/api/v1/exists/{video_id}"
    response = requests.get(URL)
    return response.json().get("exists", False)

def get_unique(results: List[video_utils.YoutubeResult]):
    """
    Check if the results are unique
    """
    import requests
    response = requests.post("http://localhost:8000/api/v1/unique", json={"ids": [result.video_id for result in results]})
    unique_ids = response.json().get("unique_ids", [])
    # return unique_ids if length greater or equal to 8, else get remain from the results
    unique_results = [result for result in results if result.video_id in unique_ids]
    if len(unique_results) >= 8:
        return unique_results[:16]
    
    not_in_unique = [result for result in results if result.video_id not in unique_ids]
    if len(not_in_unique) == 0:
        return unique_results
    
    return unique_results + not_in_unique[:16 - len(unique_results)]
        

def search_and_get_unique_videos(query: str, num_videos: int) -> List[VideoMetadata]:
    results = video_utils.search_videos(query, max_results=int(num_videos * 10))
    return get_unique(results)

import requests
def get_embeddings(description: str, clip_path: str):
    url = "http://localhost:8888/embed"
    response = requests.post(url, json={"description": description, "path": clip_path})
    return response.json()

def download_and_embed_videos(result: video_utils.YoutubeResult, query: str, video_metas: List[VideoMetadata]):
    start = time.time()
    max_retries = 3
    retries = 0
    while retries < max_retries:
        download_path = video_utils.download_video(
            result.video_id,
            start=0,
            end=min(result.length, FIVE_MINUTES),
            proxy=random.choice(PROXIES)
        )
        if download_path:
            break
    if download_path:
        clip_path = None
        try:
            result.length = video_utils.get_video_duration(download_path.name)  # correct the length
            bt.logging.info(f"Downloaded video {result.video_id} ({min(result.length, FIVE_MINUTES)}) in {time.time() - start} seconds")
            start, end = get_relevant_timestamps(query, result, download_path)
            description = get_description(result, download_path)
            clip_path = video_utils.clip_video(download_path.name, start, end)
            embeddings = get_embeddings(description, clip_path.name)
            # embeddings = imagebind.embed([description], [clip_path])
            video_metas.append(VideoMetadata(
                video_id=result.video_id,
                description=description,
                views=result.views,
                start_time=start,
                end_time=end,
                video_emb=embeddings["video"][0].tolist(),
                audio_emb=embeddings["audio"][0].tolist(),
                description_emb=embeddings["description"][0].tolist(),
            ))
            return video_metas 
        finally:
            download_path.close()
            if clip_path:
                clip_path.close()
    return None

from concurrent.futures import ThreadPoolExecutor, Future

def search_and_embed_videos(query: str, num_videos: int) -> List[VideoMetadata]:
    """
    Search YouTube for videos matching the given query and return a list of VideoMetadata objects.

    Args:
        query (str): The query to search for.
        num_videos (int, optional): The number of videos to return.

    Returns:
        List[VideoMetadata]: A list of VideoMetadata objects representing the search results.
    """
    # fetch more videos than we need
    # results = video_utils.search_videos(query, max_results=int(num_videos * 1.5))
    results = search_and_get_unique_videos(query, num_videos) 
    video_metas = []
    try:
        # take the first N that we need
        futures: List[Future] = []
        executor = ThreadPoolExecutor(max_workers=32)
        for result in results:
            future = executor.submit(download_and_embed_videos, result, query, video_metas)
            futures.append(future)
        
        # wait to get first num_videos results and cancel all pending futures
        start = time.time()
        for future  in futures:
            if future.done():
                result = future.result()
                if result:
                    video_metas = result
                    if len(video_metas) == num_videos:
                        break
            if time.time() - start > 60:
                break
            
        for future in futures:
            future.cancel()
        return results
    except Exception as e:
        bt.logging.error(f"Error searching for videos: {e}")

    return video_metas
