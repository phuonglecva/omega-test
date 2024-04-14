from pydantic import BaseModel
from fastapi import FastAPI

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
        self.imagebind = ImageBind()

    def get_embedding(self, description: str, path: str):
        with open(path, "rb") as f:
            embs = self.imagebind.embed([description], [f])
        return {
            "video": embs.video.tolist(),
            "audio": embs.audio.tolist(),
            "description": embs.description.tolist()
        }
    def get_embeddings(self, descriptions: list[str], paths: list[str]):
        embs = self.imagebind.embed(descriptions, paths)
        return {
            "video": embs.video.tolist(),
            "audio": embs.audio.tolist(),
            "description": embs.description.tolist()
        }



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
    
    uvicorn.run(app, host="0.0.0.0", port=os.getenv("PORT", 8888))