import os
from glob import glob
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

print(os.getcwd())

# root_path = os.path.join(r'//128.1.1.64', 'Document Control')
# if not os.path.exists(root_path):
#     root_path = os.path.join(r'//busse')
root_path = os.path.join(os.path.join(os.getcwd(), "documents"))
assert os.path.exists(root_path), f"Root path `{root_path}` does not exist, log into the network and try again."

root_dir = os.path.join(root_path, 'Document Control @ Busse', 'PDF Controlled Documents')

catalog = {
    # "6053": 
    #     {
    #         "mss": "749 ETAL",
    #         "ink": None, # ask yanira
    #         "print_mat": None, # ask yanira
    #         "mi": "6053",
    #         "qas": "747 ETAL",
    #         "pss": "100 ETAL",
    #         "shipper_label": "6053CSL",
    #         "dispenser_label": None,
    #         "content_label": "6053CS",
    #         "dmr": "6053"
    #     },
    # "648": 
    #     {
    #         "mss": "645-2 ETAL",
    #         "ink": "3/1000", # ask yanira
    #         "print_mat": "648UP", # ask yanira
    #         "mi": "648-1",
    #         "qas": "645 ETAL",
    #         "pss": "100 ETAL",
    #         "shipper_label": "648CSL",
    #         "dispenser_label": None,
    #         "content_label": None,
    #         "dmr": "648"
    #     }    
}

def read_in_dmrs():
    global catalog, root_path
    file = os.path.join(root_path, "dmr.xlsx")
    assert os.path.exists(file), f"DMR file `{file}` does not exist, log into the network and try again."
    
    df = pd.read_excel(file, sheet_name="Sheet1")    
    df = df.fillna("")    
    df = df.astype(str)

    df.to_excel("cleaned_dmr.xlsx", index=False)

    for index, row in df.iterrows():
        if row["dmr"] in catalog:
            print(f"Duplicate DMR found: {row['dmr']}")

        for key, value in row.items():
            value = value.strip()
            if value == "":
                value = None
            else:
                value = value.upper().lstrip("LF")
            
            if key in ["print_mat", "shipper_label", "dispenser_label", "content_label"] and value is not None:
                value = value.split(" ")[0]

            row[key] = value

        catalog[row["dmr"]] = {
            "mss": row["mss"],
            "ink": row["ink"],
            "print_mat": row["print_mat"],
            "mi": row["mi"],
            "qas": row["qas"],
            "pss": row["pss"],
            "shipper_label": row["shipper_label"],
            "dispenser_label": row["dispenser_label"],
            "content_label": row["content_label"],
            "dmr": row["dmr"],
            "special_instructions": row["special_instructions"]
        }

    print()
    print("Catalog dictionary created. with", len(catalog), "entries")
    print()

    return catalog
    
read_in_dmrs()

def user_catalog_input():
    search = False    
    while not search:
        catalog_input = input('Enter catalog number: (Q or exit to quit)\t').strip().upper()
        print()
        
        if catalog_input == 'Q' or catalog_input == 'exit':
            sys.exit()
            
        if catalog_input in catalog:            
            print("Searching for", catalog_input)
            print()
            continue_or_reset = input('Is this correct? (y/n): [Y]\t').strip().upper()
            print()
            if continue_or_reset == '':
                continue_or_reset = 'Y'
            search = True if 'Y' or 'y' in continue_or_reset else False
        else:
            print("Catalog number not found. Please try again.")
            print()
    
    return catalog_input

def search_for_files(catalog_input: str) -> list:    
    global catalog

    files = []    

    for key, file in catalog.get(catalog_input).items():
        if file is None:
            continue
        if key in ["ink"]:
            continue
        
        if key == "special_instructions" and file is not None:
            with open(f'{catalog_input}_special_instructions.txt', 'w') as f:
                f.write(file)
            files.append(f'{catalog_input}_special_instructions.txt')                

        # try as is
        pathname = os.path.join(root_dir,f'*{key.upper()}*', f'*{file}.pdf')
        if key == "qas":
            pathname = os.path.join(root_dir,f'*{key.upper()}*', '**', f'*{file}*.pdf')
        if key in ["shipper_label", "dispenser_label", "content_label", "print_mat"] :
            pathname = os.path.join(root_dir,'*DMR*', '**', f'{catalog_input}', f'*{file}*.pdf')
        if key == "dmr":
            pathname = os.path.join(root_dir,'*DMR*', '**', f'{catalog_input}', f'*{file}*DMR.pdf')

        found = glob(pathname)

        if found:
            if key in ["mss","mi", "qas"] and len(found) > 1:
                print(found[0])
                print(f"WARNING: Multiple files found for `{key}`. Using the first one found.")
                files = files + [found[0]]
            else:
                for f in found:
                    print(f)                
                files = files + found
            
            print()

        else:
            # try again with underscores
            try:
                file = file.split(" ").join("_")
            except:
                continue

            pathname = os.path.join(root_dir,f'*{key.upper()}*', f'*{file}*.pdf')        
            if key == "qas":
                pathname = os.path.join(root_dir,f'*{key.upper()}*', '**', f'*{file}*.pdf')
            if key in ["shipper_label", "dispenser_label", "content_label", "print_mat"] :
                pathname = os.path.join(root_dir,'*DMR*', '**', f'*{catalog_input}', f'*{file}*.pdf')
            if key == "dmr":
                pathname = os.path.join(root_dir,'*DMR*', '**', f'*{catalog_input}', f'*{file}*DMR.pdf')

            found = glob(pathname)

            if found:
                if key in ["mss","mi", "qas"] and len(found) > 1:
                    print(found[0])
                    print(f"WARNING: Multiple files found for `{key}`. Using the first one found.")
                    files = files + [found[0]]
                else:
                    for f in found:
                        print(f)                
                    files = files + found
                
                print()

            else:
                print(f'No files found for `{pathname}`.\n')

    # do a final sweep for all files in the dmr folder
    final_sweep = os.path.join(root_dir,'*DMR*', '**', f'*{catalog_input}', f'*.pdf')
    found = glob(final_sweep)
    if found:
        files = files + found
    
    list_of_files = os.path.join(os.getcwd(), "archive", f'{catalog_input}_list_of_files__{datetime.now():%m%d%Y%H%M%S}.txt')

    with open(list_of_files, 'w') as f:
        f.writelines([f'{x}\n' for x in files])

    files = list(set(files))    

    return files

def zip_files_for_download(catalog: str, files: list):
    import zipfile    
    
    with zipfile.ZipFile(os.path.join(os.getcwd(), "archive", f'{catalog}.zip'), 'w') as zipf:
        for file in files:
            zipf.write(file)    
    
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

    return templates.TemplateResponse("main.html", context)

@app.get("/refresh", response_class=HTMLResponse)
async def refresh_dmrs(request: Request):
    global catalog

    catalog = {}

    read_in_dmrs()

    title = "Busse File Gatherer"

    context = {
        "request": request,
        "title": title,        
    }

    return templates.TemplateResponse("main.html", context)

@app.post("/search", response_class=HTMLResponse)
async def find_in_catalog(request: Request, catalog_nbr: str = Form(...)):
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

    files = search_for_files(catalog_nbr)
    zip_files_for_download(catalog_nbr, files)

    context["files"] = files

    return templates.TemplateResponse("fragment/gathered_files.html", context)


@app.get("/download", response_class=FileResponse)
async def download_file(catalog_nbr: str):
    
    file_path = Path(os.path.join(os.getcwd(), "archive", f"{catalog_nbr}.zip"))

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=f"{catalog_nbr}__{datetime.now():%m-%d-%Y_%H%M%S}__.zip")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True)

    