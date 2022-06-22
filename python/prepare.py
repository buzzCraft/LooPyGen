#!/usr/bin/env python3
import os
from shutil import copy2
import argparse
import asyncio
import yaspin
import json
from glob import glob

from utils import Struct, generate_paths

# Parse CLI arguments
def parse_args():
    # check for command line arguments
    parser = argparse.ArgumentParser()
    input_grp = parser.add_mutually_exclusive_group(required=True)
    input_grp.add_argument('--file', help='Specify an input file', type=str)
    input_grp.add_argument('--idir', help='Specify an input directory', type=str)
    parser.add_argument('--royalty_percentage', metavar='PERCENTAGE', help='Specify the royalty percentage, required with --metadata', type=int)
    parser.add_argument('--metadata', help='Generate metadata templates instead of the CIDs list', action='store_true')
    parser.add_argument('--overwrite', help='Overwrite the metadata files and all metadata fields', action='store_true')
    parser.add_argument('--php', help=argparse.SUPPRESS, action='store_true')

    return parser.parse_args()

def load_config(args):
    cfg = Struct()

    # Input directory
    if args.file:
        cfg.input_dir, cfg.input_file = os.path.split(args.file)
    elif args.idir:
        cfg.input_dir = os.path.split(os.path.join(args.idir, ''))[0]   # Ensure no trailing '/'
    assert os.path.exists(cfg.input_dir), f'Input file/directory does not exist: {cfg.input_dir}'

    if args.metadata:
        cfg.file_filter = '*'
        assert args.royalty_percentage is not None, '--royalty_percentage is required with --metadata'
    else:
        cfg.file_filter = '*.json'

    return cfg

def make_directories(args):
    # Generate paths
    paths = generate_paths()

    # Make directories if they don't exist
    if not os.path.exists(paths.custom_output):
        os.makedirs(paths.custom_output)
    if args.metadata and not os.path.exists(paths.custom_metadata):
        os.makedirs(paths.custom_metadata)

    return paths

# CID pre-calc helper functions
async def get_file_cid(path: str, version: int=0):
    proc = await asyncio.create_subprocess_shell(
        f'cid --cid-version={version} "{path}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode > 0:
        raise RuntimeError(f'Could not get CIDv{version} of file {path}:\n\t{stderr.decode()}')
    return stdout.decode().strip()

async def get_files_cids(paths: 'list[str]', machine_readable: bool, version: int=0):
    semaphore = asyncio.Semaphore(16)   # Limit to 16 files open at once
    async def sem_task(task):
        async with semaphore:
            return await task

    task_ids = list(range(len(paths)))
    results = []

    if machine_readable:    # Make it more machine readable
        print(f"Calculating CID for {len(task_ids)} images...")
        results = await asyncio.gather( *[sem_task(get_file_cid(file, version)) for  file in paths] )
    else:   # Make it more human readable
        with yaspin.kbi_safe_yaspin().line as spinner:
            if len(task_ids) > 10:
                spinner.text = f"Calculating CID for {' '.join( [f'#{id:03}' for id in task_ids[:10]] )} (+ {len(task_ids) - 10} others)"
            else:
                spinner.text = f"Calculating CID for {' '.join( [f'#{id:03}' for id in task_ids] )}"
            results = await asyncio.gather( *[sem_task(get_file_cid(file, version)) for  file in paths] )

    return results

def main():
    # check for command line arguments
    args = parse_args()

    # Load config
    cfg = load_config(args)

    # Generate paths and make directories
    paths = make_directories(args)

    # Get list of files to process
    if cfg.input_file:
        input_files = [cfg.input_file]
    else:
        matching_files = glob(os.path.join(cfg.input_dir, cfg.file_filter))
        matching_files = list(filter(lambda f: len(os.path.splitext(f)[-1]) <= 5, matching_files))  # Remove files with extensions longer than 5 (e.g. '.json:ZoneIdentifier')
        input_files = [os.path.basename(path) for path in matching_files]

    # Extract ID from file name for all files
    ids = [int('0' + ''.join(filter(str.isdigit, f))) for f in input_files]
    # IDs for files without them are generated by adding 1 to the maximum ID found
    ids = [max(ids) + 1 + i if v == 0 else v for i, v in enumerate(ids)]

    # Sort IDs and files by IDs
    ids, input_files = list(zip(*sorted(zip(ids, input_files))))

    # Pre-calculate CIDs for input files
    cids = asyncio.run(get_files_cids( [os.path.join(cfg.input_dir, file) for file in input_files], machine_readable=args.php ))

    # Output or update metadata template files
    if args.metadata:
        for id, cid, file in zip(ids, cids, input_files):
            json_file = os.path.splitext(file)[0] + '.json'
            json_path = os.path.join(paths.custom_metadata, json_file)

            token = {}
            from_scratch = True    # Is true if 'overwrite' flag set or metadata json file is invalid
            if not args.overwrite and os.path.exists(json_path):
                try:
                    # Read all the info from file
                    with open(json_path, 'r') as infile:
                        token = json.load(infile)
                        from_scratch = False
                    print(f"Updating CIDs for {file} in {json_path} (ID #{id:03})")
                except json.JSONDecodeError as err:
                    print(f"Invalid metadata for {file} in {json_path} (ID #{id:03}): ")
                    print("  " + str(err))
            if from_scratch:    # metadata json doesn't exist or 'overwrite' flag set
                print(f'Generating new metadata for {file} to {json_path} (ID #{id:03})')
                if os.path.exists(json_path):
                    copy2(json_path, json_path + ".bak")
                    print(f"  Saving backup as {json_path + '.bak'}: ")

                # Create all new info
                token = {
                    'image': os.path.join('ipfs://', cid),
                    'animation_url': os.path.join('ipfs://', cid),
                    'name': f"COLLECTION_NAME #{id:03}",
                    'description': f"COLLECTION_DESCRIPTION",
                    'attributes': [],
                    'properties': {}
                }

            # Update CID fields
            token['image'] = os.path.join('ipfs://', cid)
            token['animation_url'] = os.path.join('ipfs://', cid)
            token['royalty_percentage'] = args.royalty_percentage

            with open(json_path, 'w+') as f:
                json.dump(token, f, indent=4)

    # Output the metadata-cids.json file for minter
    else:
        print(f'Generating metadata-cids.json file in: {paths.custom_metadata_cids}')
        with open(paths.custom_metadata_cids, 'w+') as f:
            all_cids = [{'ID': i, 'CID': c} for i,c in zip(ids, cids)]
            json.dump(all_cids, f, indent=4)

if __name__ == '__main__':
    main()