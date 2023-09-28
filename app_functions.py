# from dotenv import load_dotenv
# load_dotenv()
import os
import sys
import platform

from glob import glob
from datetime import datetime

import pandas as pd

from fastapi import HTTPException, WebSocket


LAST_UPDATED = datetime.now()

CATALOGS = {}
DOCUMENTS = {}
LINKS = {}

class WebSocketManager:
    def __init__(self):
        self.connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        await self.send_to_all({"status": "ready", "links": LINKS})

    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)

    async def send_message(self, message):
        for connection in self.connections:
            await connection.send_json(message)
    
    async def send_to_all(self, message):
        for connection in self.connections:
            await connection.send_json(message)

websocket_manager = WebSocketManager()

def current_links():
    global LINKS
    dirs = [dir for dir in os.listdir(os.path.join(os.getcwd(), "static", "files")) if "." not in dir]
    for dir in dirs:
        LINKS[dir] = build_download_links(dir)

def insensitive_glob(pattern):
    def either(c):
        return '[%s%s]' % (c.lower(), c.upper()) if c.isalpha() else c
    return glob(''.join(map(either, pattern)))

def roots():    
    root_path = os.path.join(os.path.join(os.getcwd(), "documents"))

    if not os.path.exists(os.path.join(os.getcwd(), "archive")):
        os.mkdir(os.path.join(os.getcwd(), "archive"))

    if sys.argv[-1] == "dev":
        root_path = os.path.join(r'//128.1.1.64', 'Document Control')
        if not os.path.exists(root_path):
            root_path = os.path.join(r'//busse', 'Document Control')
    elif sys.argv[-1] == "dev-wsl":
        root_path = os.path.join(r'/mnt/busse/documents')

    assert os.path.exists(root_path), f"Root path `{root_path}` does not exist, log into the network and try again."

    root_dir = os.path.join(root_path, 'Document Control @ Busse', 'PDF Controlled Documents')

    assert os.path.exists(root_dir), f"Root directory `{root_dir}` does not exist, log into the network and try again."

    return root_path, root_dir

ROOT_PATH, ROOT_DIR = roots()
STATIC_FILES = os.path.join(os.getcwd(), "static", "files")

def zip_files_for_download(catalog: str, files: list):
    import zipfile    
    
    with zipfile.ZipFile(os.path.join(STATIC_FILES, f'{catalog}.zip'), 'w') as zipf:
        for file in files:
            zipf.write(file)

def copy_files_to_static_path(catalog: str, files: list):
    import shutil

    for file in files:
        if not os.path.exists(os.path.join(STATIC_FILES, catalog)):
            os.makedirs(os.path.join(STATIC_FILES, catalog))

        shutil.copy(file, os.path.join(STATIC_FILES, catalog, os.path.basename(file)))

def read_in_dmrs():
    global CATALOGS, ROOT_PATH, DOCUMENTS, LAST_UPDATED
    
    CATALOGS = {}
    DOCUMENTS = {}            
    
    file = os.path.join(ROOT_PATH, "dmr.xlsx")     
    assert os.path.exists(file), f"DMR file `{file}` does not exist, log into the network and try again."
    
    df = pd.read_excel(file, sheet_name="Sheet1")    
    df = df.fillna("")    
    df = df.astype(str)
    
    for _, row in df.iterrows():
        if row["dmr"] in CATALOGS:
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

        CATALOGS[row["dmr"]] = {
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
    print("Catalog dictionary created. with", len(CATALOGS), "entries")    

    # go through all keys inside catalog dict and create a documents dict that is a key (document) to list of catalog numbers that use that document
    for catalog_nbr, details in CATALOGS.items():
        for key, value in details.items():
            if value is None:
                continue
            if key == "special_instructions":
                continue
            if value not in DOCUMENTS:
                DOCUMENTS[value] = []
            DOCUMENTS[value].append(catalog_nbr)

    # go through all keys in documents dict and remove duplicates and sort and uppercase
    for key, value in DOCUMENTS.items():
        DOCUMENTS[key] = list(set(value))
        DOCUMENTS[key].sort()
        DOCUMENTS[key] = [x.upper() for x in DOCUMENTS[key]]
    
    print("Documents dictionary created. with", len(DOCUMENTS), "entries")
    print()

    LAST_UPDATED = datetime.now()
    print("Last updated:", LAST_UPDATED)
    print()

def build_download_links(cat_nbr: str):    
    path = os.path.join(STATIC_FILES, cat_nbr)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Catalog number ({cat_nbr}) not found")
    if platform.system() == "Windows":        
        return [f"download/{cat_nbr}/{os.path.basename(key)}" for key in glob(os.path.join(STATIC_FILES, cat_nbr, "*"))]
    return [f"download/{cat_nbr}/{os.path.basename(key)}" for key in insensitive_glob(os.path.join(STATIC_FILES, cat_nbr, "*"))]

async def search_for_files(catalog_input: str, uuid: str) -> list:    
    global CATALOGS, ROOT_DIR

    files = []

    print(f"Searching for files for `{catalog_input}`")
    print()    
    
    details = CATALOGS.get(catalog_input, None)
    if details is None:
        raise HTTPException(status_code=404, detail=f"Catalog number ({catalog_input}) not found")
    
    print("Files found:")
    print([detail for detail in details.values() if detail is not None])

    for key, file in CATALOGS.get(catalog_input).items():
        if file is None:
            continue
        if key in ["ink"]:
            continue
        
        if key == "special_instructions" and file is not None:
            with open(os.path.join(os.getcwd(),"static", "files", f'{catalog_input}_special_instructions.txt'), 'w') as f:
                f.write(file)

        # try as is
        pathname = os.path.join(ROOT_DIR,f'*{key.upper()}*', f'*{file}.pdf')
        if key == "mi":
            pathname = os.path.join(ROOT_DIR,f'*{key.upper()}*', f'*{file}*.pdf')
        if key == "qas":
            pathname = os.path.join(ROOT_DIR,f'*{key.upper()}*', '**', f'*{file}*.pdf')
        if key in ["shipper_label", "dispenser_label", "content_label", "print_mat"] :
            pathname = os.path.join(ROOT_DIR,'*DMR*', '**', f'{catalog_input}', f'*{file}*.pdf')
        if key == "dmr":
            pathname = os.path.join(ROOT_DIR,'*DMR*', '**', f'{catalog_input}', f'*{file}*DMR.pdf')

        if platform.system() == "Windows":
            found = glob(pathname)
        else:
            found = insensitive_glob(pathname)   

        if found:
            if key in ["mss","mi", "qas"] and len(found) > 1:
                print(found[0])
                print(f"WARNING: Multiple files found for `{key}`. Using the first one found.")
                print()
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

            pathname = os.path.join(ROOT_DIR,f'*{key.upper()}*', f'*{file}.pdf')
            if key == "mi":
                pathname = os.path.join(ROOT_DIR,f'*{key.upper()}*', f'*{file}*.pdf')
            if key == "qas":
                pathname = os.path.join(ROOT_DIR,f'*{key.upper()}*', '**', f'*{file}*.pdf')
            if key in ["shipper_label", "dispenser_label", "content_label", "print_mat"] :
                pathname = os.path.join(ROOT_DIR,'*DMR*', '**', f'*{catalog_input}', f'*{file}*.pdf')
            if key == "dmr":
                pathname = os.path.join(ROOT_DIR,'*DMR*', '**', f'*{catalog_input}', f'*{file}*DMR.pdf')

            if platform.system() == "Windows":
                found = glob(pathname)
            else:
                found = insensitive_glob(pathname)   

            if found:
                if key in ["mss","mi", "qas"] and len(found) > 1:
                    print(found[0])
                    print(f"WARNING: Multiple files found for `{key}`. Using the first one found.")
                    files = files + [found[0]]
                else:
                    for f in found:
                        print(f)                
                    files = files + found                                

            else:
                print(f'No files found for `{pathname}`.\n')

    # do a final sweep for all files in the dmr folder
    final_sweep = os.path.join(ROOT_DIR,'*DMR*', '**', f'{catalog_input}', f'*.pdf')
    if platform.system() == "Windows":
        found = glob(final_sweep)
    else:
        found = insensitive_glob(final_sweep)
        
    if found:
        files = files + found
    
    files = list(set(files))

    if len(files) > 0:
        print()
        print(f"Total files found: {len(files)}")        
        for file in files:
            print(file)    

    list_of_files = os.path.join(os.getcwd(), "static", "files", f'{catalog_input}_list_of_files__{datetime.now():%m%d%Y%H%M%S}.txt')

    with open(list_of_files, 'w') as f:
        f.writelines([f'{x}\n' for x in files])
    
    print("copying files")
    copy_files_to_static_path(catalog_input, files)
    # print("zipping files")
    # zip_files_for_download(catalog_input, files)

    print("building links")
    LINKS[catalog_input] = build_download_links(catalog_input)

    # await websocket_manager.send_to_all({"status": "ready", "links": LINKS})

    await websocket_manager.send_message({"status": "complete", "uuid": uuid, "catalog": catalog_input, "links": LINKS[catalog_input]})

    return files