import argparse
import json
import logging
import math
import shutil
from typing import Optional
from pathlib import Path

from tqdm import tqdm
import requests
from pydantic import BaseModel, Field, AnyUrl, PrivateAttr, FilePath, DirectoryPath

from iiif_zero_out.settings import settings


class BBox(BaseModel):
    region_x: Optional[int] = None
    region_y: Optional[int] = None
    region_w: Optional[int] = None
    region_h: Optional[int] = None
    size_w: Optional[int] = None
    size_h: Optional[int] = None

    @property
    def region_string(self) -> str:
        if self.region_x is None:
            return "full"
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


class IIIFTile(BaseModel):
    """
    An individual tile that has both a parent IIIFImage, as well as a local filepath to be created from that downloaded image.
    """

    image_source_url: str
    image_path: Path
    bbox: BBox

    @property
    def url(self) -> str:
        return f"{self.image_source_url}/{self.bbox.url}/0/default.jpg"

    @property
    def path(self) -> Path:
        return self.image_path / self.bbox.path / "0/default.jpg"

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

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def create(self) -> None:
        if self.exists:
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        response = requests.get(self.url)
        if response.status_code != 200:
            raise Exception
        with self.path.open("wb") as img:
            img.write(response.content)

    def clean(self) -> None:
        if self.exists:
            # Must use shutil because pathlib's unlink() will not recursively remove directories
            shutil.rmtree(self.top_path)


class IIIFImage(BaseModel):
    """
    An source image that has a source IIIF Image API info.json URL to be downloaded as well as a defined set of parameters needed: scaling factors, and arbitrary custom bboxes to be downloaded
    """

    converter_domain: str
    converter_path: Path
    tile_size: int
    source_url: str
    identifier: str
    custom_tile_boxes: list[BBox] = []
    initialized: bool = False
    info: dict = {}
    tiles: list[IIIFTile] = []

    @property
    def info_exists(self) -> bool:
        return bool(self.info)

    @classmethod
    def get_scaling_factors(cls, min_dim: int, tile_size: int) -> list[int]:
        """
        Determine which scaling factors, used in the creation of partial tiles, should be created based on the original dimensions of the image.
        """

        return [
            sf for sf in settings.BASE_SCALING_FACTORS if sf <= min_dim // tile_size
        ]

    @classmethod
    def get_downsizing_levels(cls, width: int) -> list[int]:
        """
        Determine which series of small version of the image (to be used when zoomed out) should be downloaded.

        Requires requesting the original endpoint's info.json.
        """
        return [s for s in settings.BASE_SMALLER_SIZES if s < width]

    def init_default_tiles(self) -> None:
        scaling_factors = IIIFImage.get_scaling_factors(
            min_dim=self.min_dim, tile_size=self.tile_size
        )
        for sf in scaling_factors:
            cropsize = self.tile_size * sf
            full_widths = [
                (i * cropsize, cropsize, math.ceil(cropsize / sf))
                for i in range(
                    0,
                    self.info["width"] // cropsize,
                )
            ]
            remainder_width = self.info["width"] % cropsize
            if remainder_width > 0:
                full_widths.append(
                    (
                        self.info["width"] - remainder_width,
                        remainder_width,
                        math.ceil(remainder_width / sf),
                    )
                )

            full_heights = [
                (i * cropsize, cropsize)
                for i in range(0, self.info["height"] // cropsize)
            ]
            remainder_height = self.info["height"] % cropsize
            if remainder_height > 0:
                full_heights.append(
                    (self.info["height"] - remainder_height, remainder_height)
                )

            for x in full_widths:
                for y in full_heights:
                    bb = BBox(
                        region_x=x[0],
                        region_y=y[0],
                        region_w=x[1],
                        region_h=y[1],
                        size_w=x[2],
                    )
                    tile = IIIFTile(
                        image_path=self.path,
                        image_source_url=self.source_url,
                        bbox=bb,
                    )
                    self.tiles.append(tile)

    def init_fullsized_version(self) -> None:
        fullsize_tile = IIIFTile(
            image_source_url=self.source_url, image_path=self.path, bbox=BBox()
        )
        self.tiles.append(fullsize_tile)

    def init_downsized_versions(self) -> None:
        ds_levels = IIIFImage.get_downsizing_levels(width=self.info["width"])
        for ds in ds_levels:
            downsized_tile = IIIFTile(
                image_source_url=self.source_url,
                image_path=self.path,
                bbox=BBox(size_w=ds),
            )
            self.tiles.append(downsized_tile)

    def init_custom_tiles(self) -> None:
        for custom_tile in self.custom_tile_boxes:
            tile = IIIFTile(
                image_path=self.path,
                image_source_url=self.source_url,
                bbox=custom_tile,
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
                for ds in IIIFImage.get_downsizing_levels(width=input["width"])
            ],
            "tiles": [
                {
                    "scaleFactors": IIIFImage.get_scaling_factors(
                        min_dim=min(input["width"], input["height"]),
                        tile_size=self.tile_size,
                    ),
                    "width": self.tile_size,
                }
            ],
            "width": input["width"],
            "height": input["height"],
        }

        if "maxWidth" in input:
            new_info["maxWidth"] = input["maxWidth"]
        if "maxHeight" in input:
            new_info["maxHeight"] = input["maxHeight"]

        return new_info

    def get_info(self) -> None:
        self.make_dir()
        if not self.info_path.exists():
            with self.info_path.open("wb") as info_file:
                response = requests.get(self.source_info_url)
                if response.status_code != 200:
                    raise Exception(f"{response.status_code}: {response.content}")
                # Rewrite file to new specifications
                self.info = self.translate_info(response.json())
                with self.info_path.open("w") as info_file:
                    json.dump(self.info, info_file)
        with self.info_path.open("r") as info_file:
            self.info = json.load(info_file)

    def prune(self) -> None:
        """
        Remove any images not needed in the specification
        """
        target_paths: list[Path] = [t.path for t in self.tiles]
        for p in self.path.glob("**/*.jpg"):
            if p not in target_paths:
                p.unlink()

    def clean(self) -> None:
        """
        Clean this image's whole directory
        """
        shutil.rmtree(self.path)

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
    def source_info_url(self) -> str:
        return f"{self.source_url}/info.json"

    @property
    def path(self) -> Path:
        return self.converter_path / Path(self.identifier)

    @property
    def info_path(self) -> Path:
        return self.path / "info.json"

    @property
    def json(self) -> str:
        return f"{self.url}/info.json"

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def is_complete(self) -> bool:
        """
        Have all the image tiles as well as the info.json file for this image been created?
        """
        tiles_created: bool = all(t.exists for t in self.tiles)
        return tiles_created and self.info_exists

    def initialize_children(self) -> None:
        self.get_info()
        self.init_fullsized_version()
        self.init_downsized_versions()
        self.init_default_tiles()
        if bool(self.custom_tile_boxes):
            self.init_custom_tiles()
        self.initialized = True

    def create(self) -> None:
        if not self.initialized:
            logging.warning(
                f"Image {self.identifier} has not had its children tiles initialized yet"
            )
        self.prune()
        for tile in tqdm(self.tiles, leave=False):
            tile.create()

    def make_dir(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)

    def n_files_to_create(self) -> int:
        return sum([not tile.exists for tile in self.tiles])


class CustomTileSpec(BaseModel):
    url: AnyUrl
    identifier: str
    custom_tiles: list[BBox] = []


class ZeroOutConfig(BaseModel):
    output: DirectoryPath = Field(..., description="Destination directory for tiles")
    targets: FilePath = Field(..., description="JSON file containing list of ")
    domain: AnyUrl = Field(
        "http://localhost",
        description="Domain and base path to add to the '@id' attribute for every new image.",
    )
    tile_size: int = Field(
        default=512, gt=0, alias="size", description="Tile size in pixels"
    )
    clean: bool = Field(
        default=False, description="Clobber any cached JSON and tiles and start over."
    )
    sleep: float = Field(
        default=0.0,
        description="Seconds to sleep between requesting tiles from the IIIF endpoint.",
    )
    _urls: list[CustomTileSpec] = PrivateAttr(default=[])

    def read_urls(self):
        with open(self.targets, "r") as target_file:
            specs_list: list[dict] = json.load(target_file)
            self._urls = [CustomTileSpec(**d) for d in specs_list]


class ZeroConverter(BaseModel):
    """
    Manages conversion specs and state
    """

    config: ZeroOutConfig
    _images: list[IIIFImage] = PrivateAttr(default=[])

    def clean(self) -> None:
        """
        Clean the entire directory
        """
        shutil.rmtree(self.path)

    def read_urls(self) -> None:
        self.config.read_urls()

    def initialize_images(self) -> None:
        assert len(self._images) == 0
        self._images.clear()
        self.read_urls()
        for spec in self.config._urls:
            img = IIIFImage(
                converter_domain=self.config.domain,
                converter_path=self.config.output,
                source_url=spec.url,
                identifier=spec.identifier,
                tile_size=self.config.tile_size,
                custom_tile_boxes=spec.custom_tiles,
            )
            self._images.append(img)

        for image in tqdm(self._images, leave=False):
            image.initialize_children()

    def n_files_to_create(self) -> int:
        return sum([image.n_files_to_create() for image in self._images])

    @property
    def incomplete_images(self) -> list[IIIFImage]:
        """
        Return only the images that have not yet been completed
        """
        return [i for i in self._images if not i.is_complete]

    def create(self) -> None:
        logging.info(f"Creating {self.n_files_to_create()} tiles")
        for image in tqdm(self.incomplete_images, leave=False):
            image.create()
