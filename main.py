import os
from glob import glob
import sys
import pandas as pd
from datetime import datetime

root_path = os.path.join(r'//128.1.1.64', 'Document Control')
if not os.path.exists(root_path):
    root_path = os.path.join(r'//busse')
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
    global catalog
    file = os.path.join(root_path, "DMR.xlsx")
    
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
    
    files = list(set(files))

    with open(f'{catalog_input}_list_of_files__{datetime.now():%m%d%Y%H%M%S}.txt', 'w') as f:
        f.writelines([f'{x}\n' for x in files])

    return files

def zip_files_for_download(catalog: str, files: list):
    import zipfile    
    
    with zipfile.ZipFile(catalog, 'w') as zipf:
        for file in files:
            zipf.write(file)    
    

def main():
    catalog_input = user_catalog_input()
    files = search_for_files(catalog_input)
    
    zip_files_for_download(f'{catalog_input}.zip', files)

if __name__ == "__main__":
    print('base path ->', root_dir, '\n')

    main()

    