from pydantic import BaseModel
from fastapi import FastAPI

from torch.nn import functional as F
from omega.imagebind_wrapper import ImageBind

app = FastAPI()


class EmbedRequest(BaseModel):
    description: str
    path: str

class EmbedsRequest(BaseModel):
    descriptions: list[str]
    paths: list[str]


class ImageEmbeddingService:
    def __init__(self) -> None:
        device = os.getenv("DEVICE", "cuda:0")
        self.imagebind = ImageBind(device)
        
    def get_embedding(self, description: str, path: str):
        with open(path, "rb") as f:
            embs = self.imagebind.embed([description], [f])
            audio_sims = F.cosine_similarity(embs.audio, embs.description)
            print(f"audio_sims: {audio_sims}")
        return {
            "video": embs.video.tolist(),
            "audio": embs.audio.tolist(),
            "description": embs.description.tolist(),
            "audio_sims": audio_sims.tolist()
        }
    def get_embeddings(self, descriptions: list[str], paths: list[str]):
        embs = self.imagebind.embed(descriptions, paths)
        audio_sims = F.cosine_similarity(embs.audio, embs.description)
        print(f"audio_sims: {audio_sims}")
        return {
            "video": embs.video.tolist(),
            "audio": embs.audio.tolist(),
            "description": embs.description.tolist(),
            "audio_sims": audio_sims.tolist()
        }

    def get_similarity(self, embed1, embed2):
        return F.cosine_similarity(embed1, embed2).tolist()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/embed")
async def embed(request: EmbedRequest):
    return service.get_embedding(request.description, request.path)


@app.post("/embeds")
def embeds(request: EmbedsRequest):
    return service.get_embeddings(request.descriptions, request.paths)


if __name__ == "__main__":
    import uvicorn
    import os
    service = ImageEmbeddingService()
    
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8888)))