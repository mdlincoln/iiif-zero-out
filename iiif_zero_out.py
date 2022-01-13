import requests
import json
import requests
from tqdm import tqdm
import os
import shutil
from pathlib import Path
from math import floor, ceil
import logging
import optparse


BASE_SCALING_FACTORS = (1, 2, 4, 8, 16, 32, 64, 128, 256)
BASE_SMALLER_SIZES = (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)


class BBox:
    def __init__(
        self,
        region_x: int,
        region_y: int,
        region_w: int,
        region_h: int,
        size_w: int = None,
        size_h: int = None,
    ) -> None:
        self.region_x = region_x
        self.region_y = region_y
        self.region_w = region_w
        self.region_h = region_h
        self.size_w = size_w
        self.size_h = size_h

    @property
    def region_string(self) -> str:
        return f"{self.region_x},{self.region_y},{self.region_w},{self.region_h}"

    @property
    def size_string(self) -> str:
        if self.size_w is None and self.size_h is None:
            return "full"
        str_size_w: str = "" if self.size_w is None else str(self.size_w)
        str_size_h: str = "" if self.size_h is None else str(self.size_h)
        return f"{str_size_w},{str_size_h}"

    @property
    def url(self) -> str:
        return f"{self.region_string}/{self.size_string}"

    @property
    def path(self) -> Path:
        return Path(self.region_string) / Path(self.size_string)


class IIIFTile:
    """
    An individual tile that has both a parent IIIFImage, as well as a local filepath to be created from that downloaded image.
    """

    def __init__(self, image_source_url: str, image_path: Path, bbox: BBox) -> None:
        self.image_source_url = image_source_url
        self.image_path = image_path
        self.bbox = bbox

    @property
    def url(self) -> str:
        return f"{self.image_source_url}/{self.bbox.url}/0/default.jpg"

    @property
    def path(self) -> Path:
        tile_path = self.image_path / self.bbox.path / "0/default.jpg"
        return tile_path

    @property
    def dir(self) -> Path:
        """
        Immediate parent directory
        """
        return self.path.parent

    @property
    def top_path(self) -> Path:
        """
        Top-level parent directory for this tile
        """
        return self.image_path / self.bbox.path.parts[0]

    def exists(self) -> bool:
        return self.path.exists()

    def create(self) -> None:
        if self.exists():
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        response = requests.get(self.url)
        if response.status_code != 200:
            raise Exception
        with self.path.open("wb") as img:
            img.write(response.content)

    def clean(self) -> None:
        if self.exists():
            # Must use shutil because pathlib's unlink() will not recursively remove directories
            shutil.rmtree(self.top_path)


class IIIFImage:
    """
    An source image that has a source IIIF Image API info.json URL to be downloaded as well as a defined set of parameters needed: scaling factors, and arbitrary custom bboxes to be downloaded
    """

    def __init__(
        self,
        converter_domain: str,
        converter_path: Path,
        source_url: str,
        identifier: str,
        custom_tiles: list[dict] = [],
    ) -> None:
        self.converter_domain = converter_domain
        self.converter_path = converter_path
        self.source_url = source_url
        self.identifier = identifier
        self.info = {}
        self.tiles = []
        # self.generate_default_tiles()
        # self.generate_custom_tiles(custom_tiles)

    def generate_default_tiles(self) -> None:
        if not bool(self.info):
            self.get_info()

        scaling_factors: list[int] = [
            sf for sf in BASE_SCALING_FACTORS if sf < ceil(self.min_dim)
        ]

    def generate_custom_tiles(self, custom_tiles) -> None:
        for custom_tile in custom_tiles:
            tile = IIIFTile(
                image_path=self.path,
                image_source_url=self.url,
                bbox=BBox(
                    region_x=custom_tile["region_x"],
                    region_y=custom_tile["region_y"],
                    region_w=custom_tile["region_w"],
                    region_h=custom_tile["region_h"],
                    size_w=custom_tile["size_w"],
                    size_h=custom_tile["size_h"],
                ),
            )
            self.tiles.append(tile)

    def translate_info(self, input: dict) -> dict:
        new_info = {
            "@context": "http://iiif.io/api/image/2/context.json",
            "@id": f"{self.converter_domain}/{self.identifier}",
            "profile": [
                "http://iiif.io/api/image/2/level0.json",
                {"formats": ["jpg"], "qualities": ["default"]},
            ],
            "protocol": "http://iiif.io/api/image",
            "sizes": [
                {"width": ds, "height": "full"}
                for ds in []  # self.get_downsizing_levels()
            ],
            "tiles": [
                # {"scaleFactors": self.get_scaling_factors(), "width": self.tile_size}
            ],
            "width": input["width"],
            "height": input["height"],
        }
        return new_info

    def get_info(self) -> None:
        self.make_dir()
        if not self.info_path.exists():
            with self.info_path.open("wb") as info_file:
                response = requests.get(self.info_url)
                if response.status_code != 200:
                    raise Exception(f"{response.status_code}: {response.content}")
                # Rewrite file to match
                self.info = self.translate_info(response.json())
                with self.info_path.open("w") as info_file:
                    json.dump(self.info, info_file)
        with self.info_path.open("r") as info_file:
            self.info = json.load(info_file)

    def clean(self) -> None:
        """
        Clean this image's whole directory
        """
        pass

    @property
    def min_dim(self) -> int:
        if self.info is None:
            raise Exception("Info not loaded yet")
        return min(self.info["width"], self.info["height"])

    @property
    def max_dim(self) -> int:
        if self.info is None:
            raise Exception("Info not loaded yet")
        return max(self.info["width"], self.info["height"])

    @property
    def url(self) -> str:
        return f"{self.converter_domain}/{self.identifier}"

    @property
    def info_url(self) -> str:
        return f"{self.url}/info.json"

    @property
    def path(self) -> Path:
        return self.converter_path / Path(self.identifier)

    @property
    def info_path(self) -> Path:
        return self.path / "info.json"

    @property
    def json(self) -> str:
        return f"{self.url}/info.json"

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def create(self) -> None:
        if not self.exists():
            self.make_dir()
        for tile in self.tiles:
            tile.create()

    def make_dir(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)

    def n_files_to_create(self) -> int:
        return sum([tile.exists() for tile in self.tiles])


class ZeroConverter:
    """
    Accepts the
    """

    def __init__(
        self, output_path: Path, specs: list, domain: str, sleep: float = 0.0
    ) -> None:
        self.path = output_path
        self.domain = domain
        self.sleep = sleep
        self.images = []

        for spec in specs:
            custom_tiles = []
            if "custom_tiles" in specs:
                custom_tiles = spec["custom_tiles"]
            img = IIIFImage(
                converter_domain=self.domain,
                converter_path=self.path,
                source_url=spec["url"],
                identifier=spec["identifier"],
                custom_tiles=custom_tiles,
            )
            self.images.append(img)

    def clean(self) -> None:
        """
        Clean the entire directory
        """
        pass

    def n_files_to_create(self) -> int:
        return sum([image.n_files_to_create() for image in self.images])

    def create(self) -> None:
        logging.info(f"Creating {self.n_files_to_create()} tiles")
        for image in tqdm(self.images):
            image.create()


def main():
    p = optparse.OptionParser(
        description="IIIF Image API Level-0 static file generator",
        usage="usage: %prog [options] file (-h for help)",
    )

    p.add_option(
        "--output",
        "-o",
        default=None,
        action="store",
        help="Destination directory for tiles",
    )

    p.add_option(
        "--urls",
        "-u",
        default=None,
        action="store",
        help="JSON list of all URLs and identifiers",
    )

    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

    (opt, sources) = p.parse_args()

    data = json.load(open(sources[0], "r"))

    converter = ZeroConverter(
        output_path=Path(opt.output), specs=data, domain="http://localhost"
    )
    n = converter.n_files_to_create()
