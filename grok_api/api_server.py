from fastapi      import FastAPI, HTTPException
from urllib.parse import urlparse, ParseResult
from pydantic     import BaseModel
from .core         import Grok, GrokError, GrokNetworkError, GrokParsingError, GrokAuthError, GrokSessionError
from uvicorn      import run


app = FastAPI()

class ConversationRequest(BaseModel):
    proxy: str
    message: str
    model: str = "grok-3-auto"
    extra_data: dict = None

def format_proxy(proxy: str) -> str:

    if not proxy.startswith(("http://", "https://")):
        proxy: str = "http://" + proxy

    try:
        parsed: ParseResult = urlparse(proxy)

        if parsed.scheme not in ("http", "https"):
            raise ValueError("Scheme must be http or https")

        if not parsed.hostname:
            raise ValueError("Missing hostname")

        # Port is optional, will use default if missing
        if parsed.username and parsed.password:
            port_str = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}{port_str}"
        else:
            port_str = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{parsed.hostname}{port_str}"

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid proxy format: {str(e)}")

@app.post("/ask")
async def create_conversation(request: ConversationRequest):
    if not request.proxy or not request.message:
        raise HTTPException(status_code=400, detail="Proxy and message are required")

    proxy = format_proxy(request.proxy)

    try:
        answer: dict = Grok(request.model, proxy).chat(request.message, request.extra_data)

        return {
            "status": "success",
            **answer
        }
    except GrokNetworkError as e:
        raise HTTPException(status_code=502, detail=f"Grok Network Error: {str(e)}")
    except GrokParsingError as e:
        raise HTTPException(status_code=502, detail=f"Grok Parsing Error: {str(e)}")
    except GrokAuthError as e:
        raise HTTPException(status_code=401, detail=f"Grok Auth Error: {str(e)}")
    except GrokError as e:
        raise HTTPException(status_code=500, detail=f"Grok API Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

def main():
    run(app, host="0.0.0.0", port=6969)

if __name__ == "__main__":
    main()
