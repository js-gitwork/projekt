"""Kør fra projektroden: python -m projektstyring.vpmanhole.cleanup_cli [--apply]

Uden --apply er dette kun en rapport og ændrer ingen data.
"""
import argparse
import json
from projektstyring.vpmanhole.photo_service import VPManholePhotoService


def main():
    parser = argparse.ArgumentParser(description="VPManhole 40-dages-oprydning")
    parser.add_argument("--apply", action="store_true", help="Flyt udløbne fotos til karantæne")
    args = parser.parse_args()
    result = VPManholePhotoService().purge_expired_photos(dry_run=not args.apply)
    print(json.dumps({"dry_run": not args.apply, **result}, indent=2))


if __name__ == "__main__":
    main()
