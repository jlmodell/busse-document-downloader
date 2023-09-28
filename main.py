import os

import re
from glob import glob

from datetime import datetime
import platform

# from typing import Annotated
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
# from fastapi_nextauth_jwt import NextAuthJWT
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app_functions import *

# secret = os.getenv("NEXTAUTH_SECRET", None)
# assert secret is not None, "NEXTAUTH_SECRET was not set"

# JWT = NextAuthJWT(
#     secret=secret,
# )

# def print_request_cookies(request: Request):
    # print()
    # print("Cookies:")
    # for key, value in request.cookies.items():
    #     print(f"{key}: {value}")
    # print()

    # JWT = NextAuthJWT(
    #     secret=secret,
    # )

    # print(JWT)

#####################################
#####################################
###############FASTAPI###############
#####################################
#####################################

origins = [
    "http://docs.bhd-ny.com",
    "https://docs.bhd-ny.com",
    "http://localhost",
    "http://localhost:3000",
]

# middleware = [
#     Middleware(
#         CORSMiddleware,
#         allow_origins=origins,
#         allow_credentials=True,
#         allow_methods=['*'],
#         allow_headers=['*']
#     )
# ]

app = FastAPI(
    # middleware=middleware,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory=os.path.join(os.getcwd(), "static")), name="static")

# @app.middleware("http")
# async def cors_handler(request: Request, call_next):
#     response: Response = await call_next(request)
#     response.headers['Access-Control-Allow-Credentials'] = 'true'
#     response.headers['Access-Control-Allow-Origin'] = origins
#     response.headers['Access-Control-Allow-Methods'] = '*'
#     response.headers['Access-Control-Allow-Headers'] = '*'
#     return response

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:        
        while True:
            await websocket.receive_text()  # Keep the connection alive
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    global LINKS
    print("Platform:", platform.system())
    current_links()
    read_in_dmrs()    

@app.get("/")
async def index(
        # jwt: Annotated[dict, Depends(JWT)]
    ):
    return {"app_name": "busse-documents-loader-v2", "paths": ["/", "/refresh", "/search/files", "/search/swu", "/download/{catalog}"], "last_updated": f"{LAST_UPDATED:%m/%d/%Y %H:%M:%S}"}

@app.get("/refresh")
async def refresh(
        # jwt: Annotated[dict, Depends(JWT)]
    ):
    read_in_dmrs()
    return {"message": "refreshed"}

@app.get("/search/files", response_class=JSONResponse)
async def search(
        # jwt: Annotated[dict, Depends(JWT)],
        # cookies: None = Depends(print_request_cookies),
        cat_nbr: str | None = None
    ):    

    global CATALOGS
    
    keys = [key.strip().upper() for key in CATALOGS.keys()]
    keys.sort()
    
    if cat_nbr is None:
        return keys        
    
    regex = re.compile(f"^{cat_nbr}.*", re.IGNORECASE)    
    
    return [key for key in keys if regex.match(key)]

@app.get("/gather/files", response_class=JSONResponse)
async def gather_files_tasker(        
        background_tasks: BackgroundTasks, 
        # jwt: Annotated[dict, Depends(JWT)],
        # cookies: None = Depends(print_request_cookies),    
        cat_nbr: str | None = None
    ):
    
    if cat_nbr is None:
        raise HTTPException(status_code=404, detail=f"Catalog number ({cat_nbr}) not found")
    
    uuid = f"{cat_nbr}__{datetime.now():%m%d%Y%H%M%S}"
    background_tasks.add_task(search_for_files, cat_nbr, uuid)        

    await websocket_manager.send_message({"status": "gathering", "uuid": uuid, "catalog": cat_nbr})

    return uuid

@app.get("/search/swu", response_class=JSONResponse)
async def search_documents(
        # jwt: Annotated[dict, Depends(JWT)],
        doc_nbr: str
    ):

    global DOCUMENTS

    keys = [key.strip().upper() for key in DOCUMENTS.keys()]
    keys.sort()
    
    if doc_nbr is None:
        return keys     
    
    regex = re.compile(f".*{doc_nbr}.*", re.IGNORECASE)
    
    return [key for key in keys if regex.match(key)]

@app.get("/gather/swu", response_class=JSONResponse)
async def find_in_documents(
        # jwt: Annotated[dict, Depends(JWT)],
        doc_nbr: str | None = None,        
    ):

    global DOCUMENTS
    
    documents_in_use = DOCUMENTS.get(doc_nbr, None)
    
    if documents_in_use is None:
        raise HTTPException(status_code=404, detail=f"Document number ({doc_nbr}) not found")
    
    return documents_in_use

@app.get("/download/{cat_nbr}/{file_name}", response_class=FileResponse)
async def download_file(cat_nbr: str, file_name: str):
    path = os.path.join(STATIC_FILES, cat_nbr, file_name)
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Catalog number ({cat_nbr}) not found")
    
    return FileResponse(path, media_type="application/pdf", filename=file_name)

@app.get("/download/zip/{cat_nbr}", response_class=FileResponse)
async def download_zipped_file(
        cat_nbr: str,
        # jwt: Annotated[dict, Depends(JWT)]
    ):
    if platform.system() == "Windows":        
        files = [os.path.basename(key).upper() for key in glob(os.path.join(STATIC_FILES, '*.zip'))]
    else:
        files = [os.path.basename(key).upper() for key in insensitive_glob(os.path.join(STATIC_FILES, '*.zip'))]
    regex = re.compile(f".*{cat_nbr}.*", re.IGNORECASE)
    if not any(regex.match(key) for key in files):
        raise HTTPException(status_code=404, detail=f"Catalog number ({cat_nbr}) not found")    
    return FileResponse(os.path.join(STATIC_FILES, f'{cat_nbr}.zip'), media_type="application/zip", filename=f'{cat_nbr}.zip')


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8722, reload=True)
