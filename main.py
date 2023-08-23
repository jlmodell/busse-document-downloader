from datetime import datetime
import os
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import re
# import logging
# import builtins

# write logs to debug.log
# logging.basicConfig(filename=os.path.join(os.getcwd(), "logs", "debug.log"), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from cli import read_in_dmrs, search_for_files, zip_files_for_download, catalog

# def custom_print(*args, **kwargs):
#     message = ' '.join(str(arg) for arg in args)
#     logging.info(message)

# builtins.print = custom_print

if not os.path.exists(os.path.join(os.getcwd(), "logs", "today")):
    os.makedirs(os.path.join(os.getcwd(), "logs", "today"))

read_in_dmrs()

app = FastAPI()

app.mount("/static", StaticFiles(directory=os.path.join(os.getcwd(), "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(os.getcwd(), "templates"))

origins = [
    "http://localhost",
    "http://localhost:8722",
    "https://docs.bhd-ny.com/",
    "http://128.1.5.76:8722/",
    "http://128.1.5.126:8722/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    global catalog

    title = "Busse File Gatherer"

    context = {
        "request": request,
        "title": title,
    }
    
    keys = [key.strip().upper() for key in catalog.keys()]
    keys.sort()

    context["catalog"] = keys

    return templates.TemplateResponse("main.html", context)


@app.get("/refresh")
async def refresh_dmrs():

    read_in_dmrs()

    return "DMRs refreshed"


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, catalog_nbr: str):    
    global catalog

    regex = re.compile(f".*{catalog_nbr}.*", re.IGNORECASE)
    # filter catalog
    keys = [key.strip().upper() for key in catalog.keys()]
    keys.sort()

    context = {
        "request": request,
        "keys": [key for key in keys if regex.match(key)],
    }

    return templates.TemplateResponse("fragment/catalog_results.html", context)


@app.post("/search", response_class=HTMLResponse)
async def find_in_catalog(request: Request, catalog_nbr_param: str = "", catalog_nbr: str = Form(...)):
    global catalog    

    context = {
        "request": request,
    }
    
    context["details"] = {
        "mss": "None",
        "ink": "None",
        "print_mat": "None",
        "mi": "None",
        "qas": "None",
        "pss": "None",
        "shipper_label": "None",
        "dispenser_label": "None",
        "content_label": "None",
        "dmr": "None",
        "special_instructions": "None"
    }

    print({"catalog_nbr_param":catalog_nbr_param, "catalog_nbr": catalog_nbr})

    if catalog_nbr_param != "":
        catalog_nbr = catalog_nbr_param

    context["catalog_nbr"] = catalog_nbr

    details = catalog.get(catalog_nbr, None)
    if details is None:
        return templates.TemplateResponse("fragment/not_found.html", context)

    context["details"] = details

    return templates.TemplateResponse("fragment/results.html", context)

@app.post("/gather", response_class=HTMLResponse)
async def gather_files(
    request: Request,
    catalog_nbr: str = Form(...),
):
    context = {
        "request": request,
        "catalog_nbr": catalog_nbr,
    }    

    details = catalog.get(catalog_nbr, None)
    context["details"] = details

    files = search_for_files(catalog_nbr)
    zip_files_for_download(catalog_nbr, files)

    import urllib.parse

    cleaned_files = [urllib.parse.quote(file) for file in files]

    print(cleaned_files)
        
    context["files"] = cleaned_files    

    return templates.TemplateResponse("fragment/gathered_files.html", context)


@app.get("/download", response_class=FileResponse)
async def download_file(catalog_nbr: str):
    file_path = Path(os.path.join(os.getcwd(), "archive", f"{catalog_nbr}.zip"))

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=f"{catalog_nbr}__{datetime.now():%m-%d-%Y_%H%M%S}__.zip")


if __name__ == "__main__":
    import uvicorn
    import sys

    if sys.argv[-1] == "dev":
        uvicorn.run("main:app", host="0.0.0.0", port=8722, reload=True)

    

    