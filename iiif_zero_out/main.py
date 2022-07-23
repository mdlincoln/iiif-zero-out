import sys
import logging

from pydantic_cli import to_runner

from iiif_zero_out import models


def runner(config: models.ZeroOutConfig) -> int:

    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

    converter = models.ZeroOutConfig(config=config)

    if converter.config.clean:
        converter.clean()
    converter.initialize_images()
    converter.create()

    return 0


if __name__ == "__main__":
    sys.exit(
        to_runner(
            models.ZeroOutConfig,
            runner,
            version="0.1.0",
            description="IIIF Image API Level-0 static file generator",
        )(sys.argv[1:])
    )
