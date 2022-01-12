from iiif_zero_out import BBox, IIIFTile, IIIFImage, IIIFZeroer
from pathlib import Path
from tempfile import TemporaryDirectory
import requests


def test_bbox_max():
    b = BBox(region_x=10, region_y=40, region_w=45, region_h=60)
    assert b.url == "10,40,45,60/max"
    assert b.path == Path("10,40,45,60/max")


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


def test_iiif_image_base():
    outdir = TemporaryDirectory()
    outdir_path = Path(outdir.name)
    specs = [
        {
            "url": "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif",
            "identifier": "30815-primary-0-nativeres",
        }
    ]
    z = IIIFZeroer(output_path=outdir_path, specs=specs, domain="http://localhost")
    image = IIIFImage(zeroer=z, url=specs[0]["url"], identifier=specs[0]["identifier"])
    assert image.path == outdir_path / Path("30815-primary-0-nativeres")
    assert image.info_path == outdir_path / "30815-primary-0-nativeres/info.json"
    image.get_info()
    assert "width" in image.info
    assert "height" in image.info
