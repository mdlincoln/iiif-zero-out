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
def tile(tmp_path) -> IIIFTile:
    domain = "http://localhost"
    specs = [
        {
            "url": "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif",
            "identifier": "30815-primary-0-nativeres.ptif",
        }
    ]
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
    assert tile.exists() is False
    tile.create()
    assert target_path.exists()
    assert tile.exists()


def test_tile_clean(tile, tmp_path):
    assert tile.exists() is False
    tile.create()
    assert tile.exists()
    tile.clean()
    assert tile.exists() is False


"""

def test_iiif_image_base():
    outdir = TemporaryDirectory()
    outdir_path = Path(outdir.name)
    specs = [
        {
            "url": "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif",
            "identifier": "30815-primary-0-nativeres.ptif",
        }
    ]
    z = ZeroConverter(output_path=outdir_path, specs=specs, domain="http://localhost")
    image = IIIFImage(
        converter=z, source_url=specs[0]["url"], identifier=specs[0]["identifier"]
    )
    assert image.path == outdir_path / Path("30815-primary-0-nativeres.ptif")
    assert image.info_path == outdir_path / "30815-primary-0-nativeres.ptif/info.json"
    image.get_info()
    assert image.info["width"] == 487
    assert image.info["height"] == 640
    assert image.info["@id"] == "http://localhost/30815-primary-0-nativeres.ptif"


def test_iiif_tile_base():
    outdir = TemporaryDirectory()
    outdir_path = Path(outdir.name)
    specs = [
        {
            "url": "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif",
            "identifier": "30815-primary-0-nativeres.ptif",
        }
    ]
    z = ZeroConverter(output_path=outdir_path, specs=specs, domain="http://localhost")
    image = IIIFImage(
        converter=z, source_url=specs[0]["url"], identifier=specs[0]["identifier"]
    )
    bbox = BBox(region_x=100, region_y=100, region_w=120, region_h=210)
    tile = IIIFTile(image=image, bbox=bbox)
    assert (
        tile.url
        == "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif/100,100,210,210/full/0/default.jpg"
    )
    assert tile.path == outdir_path / Path("100,100,210,210/full/0/default.jpg")

"""
