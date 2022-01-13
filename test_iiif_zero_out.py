from typing import List, Dict
from iiif_zero_out import BBox, IIIFTile, IIIFImage, ZeroConverter
from pathlib import Path
from tempfile import TemporaryDirectory
import requests
import pytest
import os


def test_bbox_max():
    b = BBox(region_x=10, region_y=40, region_w=45, region_h=60)
    assert b.url == "10,40,45,60/full"
    assert b.path == Path("10,40,45,60/full")


def test_bbox_partial():
    b1 = BBox(region_x=10, region_y=40, region_w=45, region_h=60, size_h=20)
    assert b1.url == "10,40,45,60/,20"
    assert b1.path == Path("10,40,45,60/,20")
    b2 = BBox(region_x=10, region_y=40, region_w=45, region_h=60, size_w=30)
    assert b2.url == "10,40,45,60/30,"
    assert b2.path == Path("10,40,45,60/30,")


def test_bbox_exact():
    b = BBox(region_x=10, region_y=40, region_w=45, region_h=60, size_w=20, size_h=30)
    assert b.url == "10,40,45,60/20,30"
    assert b.path == Path("10,40,45,60/20,30")


@pytest.fixture
def specs() -> List[Dict]:
    return [
        {
            "url": "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif",
            "identifier": "30815-primary-0-nativeres.ptif",
        },
        {
            "url": "https://media.nga.gov/iiif/public/objects/4/6/1/3/2/46132-primary-0-nativeres.ptif/",
            "identifier": "46132-primary-0-nativeres.ptif",
            "custom_tiles": [
                {
                    "region_x": 10,
                    "region_y": 40,
                    "region_w": 45,
                    "region_h": 60,
                    "size_w": 20,
                    "size_h": 30,
                }
            ],
        },
    ]


@pytest.fixture
def tile(tmp_path, specs) -> IIIFTile:
    outdir_path = tmp_path / specs[0]["identifier"]

    test_bbox = BBox(region_x=10, region_y=40, region_w=45, region_h=60)
    return IIIFTile(
        image_source_url=specs[0]["url"], image_path=outdir_path, bbox=test_bbox
    )


def test_tile_init(tile, tmp_path):
    assert (
        tile.url
        == "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif/10,40,45,60/full/0/default.jpg"
    )
    assert (
        tile.path
        == tmp_path / "30815-primary-0-nativeres.ptif/10,40,45,60/full/0/default.jpg"
    )
    assert tile.top_path == tmp_path / "30815-primary-0-nativeres.ptif/10,40,45,60"


def test_tile_create(tile, tmp_path):
    target_path = (
        tmp_path / "30815-primary-0-nativeres.ptif/10,40,45,60/full/0/default.jpg"
    )
    assert tile.exists is False
    tile.create()
    assert target_path.exists()
    assert tile.exists


def test_tile_clean(tile):
    assert tile.exists is False
    tile.create()
    assert tile.exists
    tile.clean()
    assert tile.exists is False


@pytest.fixture
def image(tmp_path, specs) -> IIIFImage:
    return IIIFImage(
        converter_domain="http://localhost",
        converter_path=tmp_path,
        source_url=specs[0]["url"],
        identifier=specs[0]["identifier"],
        tile_size=256,
    )


@pytest.fixture
def image_with_custom(tmp_path, specs) -> IIIFImage:
    return IIIFImage(
        converter_domain="http://localhost",
        converter_path=tmp_path,
        source_url=specs[1]["url"],
        identifier=specs[1]["identifier"],
        custom_tiles=[BBox(**specs[1]["custom_tiles"][0])],
        tile_size=256,
    )


def test_iiif_image_init(image, tmp_path, specs):
    assert image.path == tmp_path / specs[0]["identifier"]
    assert image.info_path == tmp_path / specs[0]["identifier"] / "info.json"


def test_iiif_image_dir(image, tmp_path, specs):
    assert image.exists is False
    image.make_dir()
    assert image.exists


def test_iiif_image_clean(image, tmp_path, specs):
    image.make_dir()
    assert image.exists
    image.clean()
    assert image.exists is False


def test_iiif_image_info(image, tmp_path, specs):
    assert image.info_path.exists() is False
    image.get_info()
    assert image.info_path.exists() is True
    assert image.info["width"] == 487
    assert image.info["height"] == 640
    assert image.info["@id"] == "http://localhost/30815-primary-0-nativeres.ptif"


def test_iiif_image_downscales_init(image, tmp_path, specs):
    assert bool(image.tiles) is False
    image.get_info()
    image.init_downsized_versions()
    assert any(["full/256,/" in t.url for t in image.tiles])
    assert any(["full/128,/" in t.url for t in image.tiles])
    assert any(["full/64,/" in t.url for t in image.tiles])
    assert any(["full/32,/" in t.url for t in image.tiles])
    assert any(["full/16,/" in t.url for t in image.tiles])


def test_iiif_image_downscales_creation(image, tmp_path, specs):
    assert bool(image.tiles) is False
    image.get_info()
    image.init_downsized_versions()
    image.create()
    assert image.info_path.exists()
    for tile in image.tiles:
        assert tile.exists
