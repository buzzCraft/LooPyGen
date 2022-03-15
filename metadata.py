import json
import argparse
from os import path, getenv, makedirs
from dotenv import load_dotenv
from traits import names
import shutil

load_dotenv()

# check for command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--clear", help="Empty the generated directory", action="store_true")
parser.add_argument("--cid", nargs=1, help="Specify starting ID for images", type=int)
args = parser.parse_args()

dataPath = "./metadata"
genPath = dataPath + "/generated"

# Set starting ID
if args.cid:
    cid = args.cid[0]
else:
    cid = getenv("IMAGES_CID")

# Remove directories if asked to
if args.clear:
    if path.exists(genPath):
        shutil.rmtree(genPath)
    if path.exists(dataPath):
        shutil.rmtree(dataPath)

# Make paths if they don't exist
if not path.exists(genPath):
    makedirs(genPath)
if not path.exists(dataPath):
    makedirs(dataPath)


#### Generate Metadata for each Image

f = open(dataPath + '/all-traits.json',)
data = json.load(f)

# Changes this IMAGES_BASE_URL to yours
IMAGES_BASE_URL = "ipfs://" + cid + "/"
COLLECTION_LOWER = names["collection"].replace(" ", "_").lower()

def getAttribute(key, value):
    return {
        "trait_type": key,
        "value": value
    }

for i in data:
    token_id = i['ID']
    token = {
        "name": names["collection"] + ' #' + str(token_id),
        "image": IMAGES_BASE_URL + COLLECTION_LOWER + "_" + str(token_id) + '.png',
        "animation_url": IMAGES_BASE_URL + COLLECTION_LOWER + "_" + str(token_id) + '.png',
        "royalty_percentage": getenv("ROYALTY_PERCENTAGE"),
        "tokenId": token_id,
        "artist": getenv("ARTIST_NAME"),
        "minter": getenv("MINTER"),
        "attributes": [],
        "properties": {}
    }

    # set the attributes
    token["attributes"].append(getAttribute(names["layer01"], i[names["layer01"]]))
    token["attributes"].append(getAttribute(names["layer02"], i[names["layer02"]]))
    token["attributes"].append(getAttribute(names["layer03"], i[names["layer03"]]))
    token["attributes"].append(getAttribute(names["layer04"], i[names["layer04"]]))

    # set the properties
    token["properties"][names["layer01"]] = i[names["layer01"]]
    token["properties"][names["layer02"]] = i[names["layer02"]]
    token["properties"][names["layer03"]] = i[names["layer03"]]
    token["properties"][names["layer04"]] = i[names["layer04"]]

    with open(genPath + "/" + COLLECTION_LOWER + "_" + str(token_id) + ".json", 'w') as outfile:
        json.dump(token, outfile, indent=4)

f.close()