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
        custom_tile_boxes=[BBox(**specs[1]["custom_tiles"][0])],
        tile_size=512,
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


def test_iiif_image_downscales_create(image, tmp_path, specs):
    assert bool(image.tiles) is False
    image.get_info()
    image.init_downsized_versions()
    image.create()
    assert image.info_path.exists()
    for tile in image.tiles:
        assert tile.exists


def test_iiif_image_default_tiles_init(image, specs):
    assert bool(image.tiles) is False
    image.get_info()
    image.init_default_tiles()
    assert f"{specs[0]['url']}/0,0,256,256/256,/0/default.jpg" in [
        t.url for t in image.tiles
    ]
    assert f"{specs[0]['url']}/0,256,256,256/256,/0/default.jpg" in [
        t.url for t in image.tiles
    ]
    assert f"{specs[0]['url']}/0,512,256,128/256,/0/default.jpg" in [
        t.url for t in image.tiles
    ]
    assert f"{specs[0]['url']}/256,0,231,256/231,/0/default.jpg" in [
        t.url for t in image.tiles
    ]
    assert f"{specs[0]['url']}/256,256,231,256/231,/0/default.jpg" in [
        t.url for t in image.tiles
    ]
    assert f"{specs[0]['url']}/256,512,231,128/231,/0/default.jpg" in [
        t.url for t in image.tiles
    ]


def test_iiif_image_default_tiles_create(image, specs):
    assert bool(image.tiles) is False
    image.get_info()
    image.init_default_tiles()
    image.create()
    assert image.info_path.exists()
    for tile in image.tiles:
        assert tile.exists


def test_iiif_image_custom_tiles_create(image_with_custom):
    assert bool(image_with_custom.tiles) is False
    image_with_custom.get_info()
    image_with_custom.initialize_children()
    w = 12048
    h = 17847
    n_target_tiles = (
        ((w // 512 + 1) * (h // 512 + 1))
        + ((w // 1024 + 1) * (h // 1024 + 1))
        + ((w // 2048 + 1) * (h // 2048 + 1))
        + ((w // 4096 + 1) * (h // 4096 + 1))
        + ((w // 8192 + 1) * (h // 8192 + 1))
        + 1  # custom tile
        + 10  # downsized variations
    )
    assert image_with_custom.n_files_to_create() == n_target_tiles
    assert all([not t.exists for t in image_with_custom.tiles])
    assert image_with_custom.is_complete is False


def test_iiif_image_partial(image):
    image.initialize_children()
    n_to_create = image.n_files_to_create()
    image.tiles[0].create()
    image.tiles[1].create()
    assert image.n_files_to_create() == n_to_create - 2
