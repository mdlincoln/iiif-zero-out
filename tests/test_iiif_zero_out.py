from pathlib import Path

import pytest

from iiif_zero_out.models import BBox, IIIFTile, IIIFImage, ZeroConverter


class TestBBox:
    def test_bbox_max(self):
        b = BBox(region_x=10, region_y=40, region_w=45, region_h=60)
        assert b.url == "10,40,45,60/full"
        assert b.path == Path("10,40,45,60/full")

    def test_bbox_partial(self):
        b1 = BBox(region_x=10, region_y=40, region_w=45, region_h=60, size_h=20)
        assert b1.url == "10,40,45,60/,20"
        assert b1.path == Path("10,40,45,60/,20")
        b2 = BBox(region_x=10, region_y=40, region_w=45, region_h=60, size_w=30)
        assert b2.url == "10,40,45,60/30,"
        assert b2.path == Path("10,40,45,60/30,")

    def test_bbox_exact(self):
        b = BBox(
            region_x=10, region_y=40, region_w=45, region_h=60, size_w=20, size_h=30
        )
        assert b.url == "10,40,45,60/20,30"
        assert b.path == Path("10,40,45,60/20,30")


@pytest.fixture
def specs() -> list[dict]:
    return [
        {
            "url": "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif",
            "identifier": "30815-primary-0-nativeres.ptif",
        },
        {
            "url": "https://media.nga.gov/iiif/640/public/objects/1/5/7/0/4/3/157043-primary-0-nativeres.ptif",
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


class TestTile:
    def test_tile_init(self, tile, tmp_path):
        assert (
            tile.url
            == "https://media.nga.gov/iiif/public/objects/3/0/8/1/5/30815-primary-0-nativeres.ptif/10,40,45,60/full/0/default.jpg"
        )
        assert (
            tile.path
            == tmp_path
            / "30815-primary-0-nativeres.ptif/10,40,45,60/full/0/default.jpg"
        )
        assert tile.top_path == tmp_path / "30815-primary-0-nativeres.ptif/10,40,45,60"

    def test_tile_create(self, tile, tmp_path):
        target_path = (
            tmp_path / "30815-primary-0-nativeres.ptif/10,40,45,60/full/0/default.jpg"
        )
        assert tile.exists is False
        tile.create()
        assert target_path.exists()
        assert tile.exists

    def test_tile_clean(self, tile):
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
        tile_size=128,
    )


class TestImage:
    def test_iiif_image_init(self, image, tmp_path, specs):
        assert image.path == tmp_path / specs[0]["identifier"]
        assert image.info_path == tmp_path / specs[0]["identifier"] / "info.json"

    def test_iiif_image_dir(self, image, tmp_path, specs):
        assert image.exists is False
        image.make_dir()
        assert image.exists

    def test_iiif_image_clean(self, image, tmp_path, specs):
        image.make_dir()
        assert image.exists
        image.clean()
        assert image.exists is False

    def test_iiif_image_info(self, image, tmp_path, specs):
        assert image.info_path.exists() is False
        image.get_info()
        assert image.info_path.exists() is True
        assert image.info["width"] == 487
        assert image.info["height"] == 640
        assert image.info["@id"] == "http://localhost/30815-primary-0-nativeres.ptif"

    def test_iiif_image_fullsize_init(self, image):
        assert bool(image.tiles) is False
        image.get_info()
        image.init_fullsized_version()
        assert any(["full/full/" in t.url for t in image.tiles])

    def test_iiif_image_downscales_init(self, image, tmp_path, specs):
        assert bool(image.tiles) is False
        image.get_info()
        image.init_downsized_versions()
        assert any(["full/256,/" in t.url for t in image.tiles])
        assert any(["full/128,/" in t.url for t in image.tiles])
        assert any(["full/64,/" in t.url for t in image.tiles])
        assert any(["full/32,/" in t.url for t in image.tiles])
        assert any(["full/16,/" in t.url for t in image.tiles])

    def test_iiif_image_downscales_create(self, image, tmp_path, specs):
        assert bool(image.tiles) is False
        image.get_info()
        image.init_downsized_versions()
        image.create()
        assert image.info_path.exists()
        for tile in image.tiles:
            assert tile.exists

    def test_iiif_image_default_tiles_init(self, image, specs):
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

    def test_iiif_image_default_tiles_create(self, image, specs):
        assert bool(image.tiles) is False
        image.get_info()
        image.init_default_tiles()
        image.create()
        assert image.info_path.exists()
        for tile in image.tiles:
            assert tile.exists

    def test_iiif_image_custom_tiles_create(self, image_with_custom):
        assert bool(image_with_custom.tiles) is False
        image_with_custom.get_info()
        image_with_custom.initialize_children()
        w = 640
        h = 472
        n_target_tiles = (
            ((w // 128) * (h // 128 + 1))
            + ((w // 256 + 1) * (h // 256 + 1))
            + 1  # custom tile
            + 7  # downsized variations
        )
        # Confirm that custom tile was successfully created
        assert image_with_custom.n_files_to_create() == n_target_tiles
        assert all([not t.exists for t in image_with_custom.tiles])
        assert image_with_custom.is_complete is False
        image_with_custom.create()
        assert any(
            ["10,40,45,60/20,30" in str(p.path) for p in image_with_custom.tiles]
        )

    def test_iiif_image_partial(self, image):
        image.initialize_children()
        n_to_create = image.n_files_to_create()
        image.tiles[0].create()
        image.tiles[1].create()
        assert image.n_files_to_create() == n_to_create - 2


@pytest.fixture
def converter(specs, tmp_path) -> ZeroConverter:
    return ZeroConverter(
        output_path=tmp_path, specs=specs, domain="http://localhost", tile_size=256
    )


@pytest.fixture
def large_converter(specs, tmp_path) -> ZeroConverter:
    return ZeroConverter(
        output_path=tmp_path, specs=specs, domain="http://localhost", tile_size=1024
    )


class TestConverter:
    def test_iiif_converter_init(self, converter):
        assert len(converter.images) == 2
        assert converter.n_files_to_create() == 0
        assert all([not i.initialized for i in converter.images])
        converter.initialize_images()
        assert all([i.initialized for i in converter.images])
        assert converter.n_files_to_create() > 0

    def test_large_zero_converter(self, large_converter):
        large_converter.initialize_images()
        for i in large_converter.images:
            for t in i.tiles:
                "/1024,/0" in str(i.path)

    def test_iiif_converter_create(self, converter):
        converter.initialize_images()
        converter.create()
        for image in converter.images:
            assert image.is_complete
