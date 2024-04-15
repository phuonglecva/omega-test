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
    print(f"Got {len(results)} results")
    return get_unique(results)

import requests
def get_embeddings(description: str, clip_path: str):
    url = "http://localhost:8888/embed"
    response = requests.post(url, json={"description": description, "path": clip_path})
    return response.json()
def get_random_proxy():
    response = requests.get("http://localhost:8000/api/v1/proxies/random")
    return response.json().get("proxy", None)


def parallel_download_videos(results: List[video_utils.YoutubeResult], max_result: int = 8):
    # parallel downdload videos from list of results and return list of video paths, if success reach 8 videos, return the list and cancel all pending downloads
    executor = ThreadPoolExecutor(max_workers=10)
    video_paths = {}
    for result in results:
        print(f"Downloading video {result.video_id}")
        future = executor.submit(video_utils.download_video, result.video_id, start=0, end=min(result.length, FIVE_MINUTES), proxy=get_random_proxy())
        video_paths[result.video_id] = future
    start = time.time()
    is_ok = False
    final_result = {}
    while True:
        all_done = True
        for video_id, future in video_paths.items():
            if not future.done():
                all_done = False
                
            if future.done():
                path = future.result()
                if path:
                    final_result[video_id] = (result, path)
                    if len(final_result.keys()) == max_result:
                        is_ok = True
                        break
        if is_ok or all_done:
            print(f"Done downloading videos in {time.time() - start} seconds")
            break
    print(f"Final result: {final_result}, Length: {len(final_result.keys())}")
    return final_result

def embedding_videos(result: video_utils.YoutubeResult, download_path: any):
    start = time.time()
    clip_path = None
    print(f"Start embedding video {result.video_id}")
    try:
        result.length = video_utils.get_video_duration(download_path.name)  # correct the length
        # bt.logging.info(f"Downloaded video {result.video_id} ({min(result.length, FIVE_MINUTES)}) in {time.time() - start} seconds")
        start, end = get_relevant_timestamps(None, result, download_path)
        description = get_description(result, download_path)
        clip_path = video_utils.clip_video(download_path.name, start, end)
        embeddings = get_embeddings(description, clip_path.name)
        print(f"Done embedding video {result.video_id} in {time.time() - start} seconds")
        return VideoMetadata(
            video_id=result.video_id,
            description=description,
            views=result.views,
            start_time=start,
            end_time=end,
            video_emb=embeddings["video"][0],
            audio_emb=embeddings["audio"][0],
            description_emb=embeddings["description"][0],
        )
    except Exception as e:
        bt.logging.error(f"Error embedding video: {e}")
        return None
    finally:
        download_path.close()
        if clip_path:
            clip_path.close()
    

def download_and_embed_videos(result: video_utils.YoutubeResult, query: str):
    start = time.time()
    max_retries = 3
    retries = 0
    
    while retries < max_retries:
        proxy = get_random_proxy()
        download_path = video_utils.download_video(
            result.video_id,
            start=0,
            end=min(result.length, FIVE_MINUTES),
            proxy=proxy
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
            return VideoMetadata(
                video_id=result.video_id,
                description=description,
                views=result.views,
                start_time=start,
                end_time=end,
                video_emb=embeddings["video"][0],
                audio_emb=embeddings["audio"][0],
                description_emb=embeddings["description"][0],
            )
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
    start = time.time()
    executor = ThreadPoolExecutor(max_workers=4)
    try:
        # download and embed videos in parallel
        video_paths = parallel_download_videos(results)
        embed_futures = []
        for _, (result, path) in video_paths.items():
            embed_futures.append(executor.submit(embedding_videos, result, path))
        for future in embed_futures:
            try:
                video_meta = future.result()
                if video_meta:
                    video_metas.append(video_meta)
            except Exception as e:
                bt.logging.error(f"Error embedding video: {e}")
                continue      
            
    except Exception as e:
        bt.logging.error(f"Error searching for videos: {e}")

    print(f"Done embedding {len(video_metas)} videos in {time.time() - start} seconds")   
    return video_metas
