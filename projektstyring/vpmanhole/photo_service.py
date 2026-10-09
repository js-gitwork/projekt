from __future__ import annotations

import os
import re
import shutil
import tempfile

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from projektstyring.backend.db_models import (
    Installation,
    Manhole,
    Stretch,
    VPManholeDelivery,
    VPManholePhoto,
)
from zipfile import ZIP_DEFLATED, ZipFile


PhotoType = Literal[
    "before",
    "during",
    "after",
    "cover",
]


PHOTO_FILENAMES = {
    "before": "Før.jpg",
    "after": "Efter.jpg",
    "cover": "Dæksel.jpg",
}


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


class PhotoServiceError(Exception):
    """Fejl ved validering eller håndtering af brøndfotos."""


class VPManholePhotoService:

    def __init__(
        self,
        storage_root: str | Path | None = None,
    ):
        configured_root = (
            storage_root
            if storage_root is not None
            else os.environ.get(
                "VPMANHOLE_PHOTO_ROOT",
                "/var/lib/vpmanhole/photos",
            )
        )

        self.storage_root = Path(configured_root).resolve()

    @staticmethod
    def _safe_component(value: str) -> str:
        """
        Gør projekt-, brønd- og installationsnumre
        sikre at anvende som mappekomponenter.
        """
        value = re.sub(
            r'[\\/:\*?"<>|\x00-\x1f]',
            "_",
            str(value),
        ).strip(" .")

        if not value or value in {".", ".."}:
            raise PhotoServiceError(
                "Ugyldigt mappenavn"
            )

        return value

    @staticmethod
    def _filename(
        photo_type: PhotoType,
        sequence: int,
    ) -> str:
        """
        Bestemmer billedets faste filnavn.
        """
        if photo_type not in {
            "before",
            "during",
            "after",
            "cover",
        }:
            raise PhotoServiceError(
                "Ukendt billedtype"
            )

        if sequence < 1:
            raise PhotoServiceError(
                "Ugyldigt billednummer"
            )

        if photo_type == "during":
            return f"Igangværende{sequence}.jpg"

        if sequence != 1:
            raise PhotoServiceError(
                "Denne billedtype kan kun have ét billede"
            )

        return PHOTO_FILENAMES[photo_type]

    @staticmethod
    def _installation_contains_manhole(
        session: Session,
        installation_id: int,
        manhole_id: int,
    ) -> bool:
        """
        Kontrollerer at brønden er knyttet til
        installationen via en strækning.
        """
        statement = (
            select(Stretch.id)
            .where(
                Stretch.installation_id == installation_id,
                (
                    (Stretch.bottom_manhole_id == manhole_id)
                    | (Stretch.top_manhole_id == manhole_id)
                ),
            )
            .limit(1)
        )

        return session.scalar(statement) is not None

    @staticmethod
    def _first_installation_id(
        session: Session,
        project_id: str,
        manhole_id: int,
    ) -> int:
        """
        Finder den første aktive installation,
        som brønden er knyttet til.

        EXISTS undgår dubletter fra strækninger
        og bevarer sortering efter installationsrækkefølge.

        Dette erstatter den tidligere kombination af
        SELECT DISTINCT og ORDER BY, som PostgreSQL
        ikke accepterede.
        """
        linked_stretch = (
            select(Stretch.id)
            .where(
                Stretch.installation_id == Installation.id,
                (
                    (Stretch.bottom_manhole_id == manhole_id)
                    | (Stretch.top_manhole_id == manhole_id)
                ),
            )
            .exists()
        )

        statement = (
            select(Installation.id)
            .where(
                Installation.project_id == project_id,
                Installation.active.is_(True),
                linked_stretch,
            )
            .order_by(
                Installation.sequence.asc(),
                Installation.id.asc(),
            )
            .limit(1)
        )

        installation_id = session.scalar(statement)

        if installation_id is None:
            raise PhotoServiceError(
                "Brønden har ingen aktiv installation"
            )

        return installation_id

    def _get_or_create_delivery(
        self,
        session: Session,
        project_id: str,
        installation_id: int,
        manhole_id: int,
    ) -> VPManholeDelivery:
        """
        Finder eller opretter afleveringsregistreringen
        for en fysisk brønd.

        En brønd har kun én afleveringsregistrering,
        selvom den indgår i flere installationer.
        """

        # Lås brønden, så samtidige uploads ikke
        # opretter flere afleveringsregistreringer.
        manhole = session.scalar(
            select(Manhole)
            .where(Manhole.id == manhole_id)
            .with_for_update()
        )

        installation = session.get(
            Installation,
            installation_id,
        )

        if (
            manhole is None
            or installation is None
            or manhole.project_id != project_id
            or installation.project_id != project_id
            or not manhole.active
            or not installation.active
        ):
            raise PhotoServiceError(
                "Brønd eller installation findes ikke i projektet"
            )

        if not self._installation_contains_manhole(
            session,
            installation_id,
            manhole_id,
        ):
            raise PhotoServiceError(
                "Brønden hører ikke til installationen"
            )

        delivery = session.scalar(
            select(VPManholeDelivery).where(
                VPManholeDelivery.manhole_id == manhole_id
            )
        )

        if delivery is None:
            first_installation_id = (
                self._first_installation_id(
                    session,
                    project_id,
                    manhole_id,
                )
            )

            delivery = VPManholeDelivery(
                manhole_id=manhole_id,
                folder_installation_id=first_installation_id,
                is_completed=False,
            )

            session.add(delivery)
            session.flush()

        return delivery

    def _folder(
        self,
        session: Session,
        project_id: str,
        delivery: VPManholeDelivery,
    ) -> Path:
        """
        Returnerer brøndens faste lagermappe.

        Mappestruktur:
            <lager>/<projekt>/<brøndnr> Inst. <installationsnr>
        """
        manhole = session.get(
            Manhole,
            delivery.manhole_id,
        )

        installation = session.get(
            Installation,
            delivery.folder_installation_id,
        )

        if manhole is None or installation is None:
            raise PhotoServiceError(
                "Manglende brønd eller installation"
            )

        folder_name = (
            f"{self._safe_component(manhole.manhole_no)} "
            f"Inst. "
            f"{self._safe_component(installation.installation_no)}"
        )

        folder = (
            self.storage_root
            / self._safe_component(project_id)
            / folder_name
        ).resolve()

        if not folder.is_relative_to(self.storage_root):
            raise PhotoServiceError(
                "Ugyldig lagersti"
            )

        return folder

    @staticmethod
    def _convert_to_jpeg(
        image_bytes: bytes,
    ) -> bytes:
        """
        Kontrollerer og konverterer billedet til JPEG.

        - Maksimalt 20 MB upload
        - Maksimalt 40 millioner pixels
        - Korrekt orientering fra kameraets EXIF
        - Konvertering til RGB
        - JPEG-kvalitet 85
        """
        if (
            not image_bytes
            or len(image_bytes) > MAX_UPLOAD_BYTES
        ):
            raise PhotoServiceError(
                "Billedet er tomt eller større end 20 MB"
            )

        try:
            with Image.open(
                BytesIO(image_bytes)
            ) as source:

                if (
                    source.width * source.height
                    > MAX_IMAGE_PIXELS
                ):
                    raise PhotoServiceError(
                        "Billedets opløsning er for høj"
                    )

                image = ImageOps.exif_transpose(source)

                if image.mode != "RGB":
                    image = image.convert("RGB")

                output = BytesIO()

                image.save(
                    output,
                    format="JPEG",
                    quality=85,
                )

                return output.getvalue()

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ) as exc:
            raise PhotoServiceError(
                "Filen er ikke et gyldigt billede"
            ) from exc

    def create_export_zip(
        self,
        project_id: str,
        selected_folders: list[str] | None = None,
    ) -> Path:
        """
        Opretter ZIP med brøndbilleder.

        selected_folders:
            None = alle brøndmapper
            Liste = kun de valgte brøndmapper

        ZIP-struktur:
            Brønde-V999999/
                381100S Inst. 8/
                    Før.jpg
                    Efter.jpg
                    Dæksel.jpg
        """
        safe_project_id = self._safe_component(project_id)

        project_folder = (
            self.storage_root / safe_project_id
        ).resolve()

        if not project_folder.is_relative_to(self.storage_root):
            raise PhotoServiceError("Ugyldig projektsti")

        if not project_folder.is_dir():
            raise PhotoServiceError(
                "Projektet har endnu ingen billedmapper"
            )

        folders = sorted(
            (
                folder
                for folder in project_folder.iterdir()
                if folder.is_dir() and not folder.is_symlink()
            ),
            key=lambda folder: folder.name.casefold(),
        )

        if selected_folders is not None:
            selected = {
                self._safe_component(name)
                for name in selected_folders
            }

            folders = [
                folder
                for folder in folders
                if folder.name in selected
            ]

            if len(folders) != len(selected):
                raise PhotoServiceError(
                    "En eller flere valgte brøndmapper findes ikke"
                )

        if not folders:
            raise PhotoServiceError(
                "Ingen brøndmapper valgt til eksport"
            )

        with tempfile.NamedTemporaryFile(
            prefix="vpmanhole_export_",
            suffix=".zip",
            delete=False,
        ) as temporary:
            zip_path = Path(temporary.name)

        root_name = f"Brønde-{safe_project_id}"
        image_count = 0

        try:
            with ZipFile(
                zip_path,
                mode="w",
                compression=ZIP_DEFLATED,
            ) as archive:
                for folder in folders:
                    for photo_path in sorted(folder.iterdir()):
                        if (
                            not photo_path.is_file()
                            or photo_path.is_symlink()
                            or photo_path.suffix.lower() != ".jpg"
                        ):
                            continue

                        archive.write(
                            photo_path,
                            arcname=(
                                f"{root_name}/"
                                f"{folder.name}/"
                                f"{photo_path.name}"
                            ),
                        )
                        image_count += 1

            if image_count == 0:
                raise PhotoServiceError(
                    "Ingen billeder fundet til eksport"
                )

            return zip_path

        except Exception:
            zip_path.unlink(missing_ok=True)
            raise

    def save_photo(
        self,
        session: Session,
        *,
        project_id: str,
        installation_id: int,
        manhole_id: int,
        photo_type: PhotoType,
        image_bytes: bytes,
        user_id: int,
        sequence: int = 1,
    ) -> VPManholePhoto:
        """
        Gemmer et brøndfoto og dets metadata.

        Sessionen skal være dedikeret til denne operation.

        Metoden håndterer selv commit og rollback.

        API-ruten er ansvarlig for:
        - Login
        - Rolle
        - CSRF
        - Begrænsning af uploadstørrelse
        """

        filename = self._filename(
            photo_type,
            sequence,
        )

        jpeg_bytes = self._convert_to_jpeg(
            image_bytes
        )

        temporary_path: Path | None = None
        backup_path: Path | None = None
        target: Path | None = None

        replaced = False
        committed = False

        try:
            delivery = self._get_or_create_delivery(
                session,
                project_id,
                installation_id,
                manhole_id,
            )

            folder = self._folder(
                session,
                project_id,
                delivery,
            )

            folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            target = folder / filename

            relative_path = target.relative_to(
                self.storage_root
            ).as_posix()

            photo = session.scalar(
                select(VPManholePhoto).where(
                    VPManholePhoto.delivery_id == delivery.id,
                    VPManholePhoto.photo_type == photo_type,
                    VPManholePhoto.sequence == sequence,
                )
            )

            if photo is None:
                photo = VPManholePhoto(
                    delivery_id=delivery.id,
                    photo_type=photo_type,
                    sequence=sequence,
                    relative_path=relative_path,
                    uploaded_by_user_id=user_id,
                )

                session.add(photo)

            else:
                photo.relative_path = relative_path
                photo.uploaded_by_user_id = user_id
                photo.uploaded_at = datetime.now(
                    timezone.utc
                )

            # Skriv først billedet til en midlertidig fil
            # i samme mappe som den endelige fil.
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=folder,
                prefix=".upload_",
                suffix=".tmp",
                delete=False,
            ) as temporary:

                temporary.write(jpeg_bytes)

                temporary_path = Path(
                    temporary.name
                )

            # Hvis billedet allerede findes, bevarer vi
            # en sikkerhedskopi indtil database-commit.
            if target.exists():
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=folder,
                    prefix=".backup_",
                    suffix=".tmp",
                    delete=False,
                ) as backup:

                    backup_path = Path(
                        backup.name
                    )

                shutil.copy2(
                    target,
                    backup_path,
                )

            # Udskift billedet atomisk.
            os.replace(
                temporary_path,
                target,
            )

            temporary_path = None
            replaced = True

            # Gem metadata i databasen.
            session.commit()
            committed = True

            session.refresh(photo)

            return photo

        except Exception:
            if not committed:
                session.rollback()

                # Genskab det tidligere billede,
                # hvis databaseoperationen fejlede.
                if replaced and target is not None:

                    if backup_path is not None:
                        os.replace(
                            backup_path,
                            target,
                        )

                        backup_path = None

                    else:
                        target.unlink(
                            missing_ok=True
                        )

            raise

        finally:
            if temporary_path is not None:
                temporary_path.unlink(
                    missing_ok=True
                )

            if backup_path is not None:
                backup_path.unlink(
                    missing_ok=True
                )