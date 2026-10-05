from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


class ChangeGroundingError(ValueError):
    """
    Rejses, når en foreslået ændring ikke kan forankres i brugerens
    besked eller den aktive samtalekontekst.
    """


class ScenarioChangeGrounder:
    """
    Kontrollerer, at AI-genererede ændringer er forankret i kildeteksten.

    Interpreteren skal for hver faktisk værdi angive:

    {
        "target": "team_id",
        "quote": "Led 1",
        "source": "question"
    }

    Grounderen kontrollerer, at citatet faktisk findes i den angivne
    kilde. Den afgør ikke, om holdet eller projektet eksisterer; det er
    ScenarioChangeResolverens ansvar.
    """

    SUPPORTED_SOURCES = {
        "question",
        "context",
    }

    def ground_changes(
        self,
        *,
        question: str,
        changes: list[dict[str, Any]],
        conversation_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Returnerer ændringerne, hvis alle nødvendige værdier er grounded.

        Ingen ændringer foretages i systemet.
        """

        normalized_question = str(
            question or ""
        ).strip()

        if not normalized_question:
            raise ChangeGroundingError(
                "Brugerens oprindelige besked mangler."
            )

        if not isinstance(changes, list) or not changes:
            raise ChangeGroundingError(
                "Der er ingen ændringer at kontrollere."
            )

        context_text = json.dumps(
            conversation_context or {},
            ensure_ascii=False,
            default=str,
        )

        grounded_changes = []

        for sequence, change in enumerate(
            changes,
            start=1,
        ):
            grounded_changes.append(
                self._ground_change(
                    change=change,
                    sequence=sequence,
                    question=normalized_question,
                    context_text=context_text,
                )
            )

        return grounded_changes

    def _ground_change(
        self,
        *,
        change: dict[str, Any],
        sequence: int,
        question: str,
        context_text: str,
    ) -> dict[str, Any]:
        if not isinstance(change, dict):
            raise ChangeGroundingError(
                f"Ændring {sequence} er ikke struktureret korrekt."
            )

        change_type = str(
            change.get("change_type") or ""
        ).strip()

        grounding = change.get("grounding")

        if not isinstance(grounding, list):
            raise ChangeGroundingError(
                f"Ændring {sequence} mangler grounding."
            )

        evidence_by_target = (
            self._validate_grounding_entries(
                grounding=grounding,
                sequence=sequence,
                question=question,
                context_text=context_text,
            )
        )

        required_targets = (
            self._required_grounding_targets(
                change
            )
        )

        missing_targets = [
            target
            for target in required_targets
            if target not in evidence_by_target
        ]

        if missing_targets:
            raise ChangeGroundingError(
                f"Ændring {sequence} mangler tekstgrundlag for: "
                f"{', '.join(missing_targets)}."
            )

        grounded = deepcopy(change)

        grounded["metadata"] = {
            **deepcopy(
                change.get("metadata")
                or {}
            ),
            "grounding_verified": True,
            "grounding_targets": sorted(
                evidence_by_target
            ),
        }

        return grounded

    def _validate_grounding_entries(
        self,
        *,
        grounding: list[Any],
        sequence: int,
        question: str,
        context_text: str,
    ) -> dict[str, dict[str, str]]:
        """
        Validerer grounding-citater og grupperer dem efter target.

        Strukturelle dele af change-kontrakten, fx feltnavne,
        er ikke brugerdata og skal derfor ikke tekst-groundes.
        De valideres senere af scenariemotorens egne whitelists.
        """

        result = {}

        structural_targets = {
            "field",
            "after.field",
            "change_type",
            "target_type",
        }

        for item in grounding:
            if not isinstance(item, dict):
                continue

            target = str(
                item.get("target") or ""
            ).strip()

            if target in structural_targets:
                continue

            quote = str(
                item.get("quote") or ""
            ).strip()

            source = str(
                item.get("source") or "question"
            ).strip()

            if not target or not quote:
                continue

            if source not in self.SUPPORTED_SOURCES:
                raise ChangeGroundingError(
                    f"Ændring {sequence} har en ukendt "
                    f"grounding-kilde: '{source}'."
                )

            source_text = (
                question
                if source == "question"
                else context_text
            )

            if not self._contains_quote(
                source_text,
                quote,
            ):
                raise ChangeGroundingError(
                    f"Ændring {sequence} bruger værdien "
                    f"'{quote}', men teksten findes ikke i "
                    f"{'brugerens besked' if source == 'question' else 'samtalekonteksten'}."
                )

            result[target] = {
                "quote": quote,
                "source": source,
            }

        return result

    def _required_grounding_targets(
        self,
        change: dict[str, Any],
    ) -> set[str]:
        """
        Bestemmer hvilke faktiske bruger-/domæneværdier
        ændringstypen kræver tekstgrundlag for.

        Strukturelle værdier som change_type, target_type og field
        groundes ikke. De valideres af scenariemotorens kontrakt
        og felt-whitelists.
        """

        change_type = str(
            change.get("change_type") or ""
        ).strip()

        required = {
            "project_id",
        }

        if change_type == "project_field_change":
            required.add("after.value")

        elif change_type == "installation_field_change":
            selection = change.get("selection")

            has_all_selection = (
                isinstance(selection, dict)
                and str(
                    selection.get("type") or ""
                ).strip() == "all"
            )

            if has_all_selection:
                required.add("selection")
            else:
                required.add("installation_id")

            required.add("after.value")

        elif change_type == "manhole_field_change":
            required.add("manhole_no")
            required.add("after.value")

        elif change_type == "task_assignment_change":
            required.add("installation_id")
            required.add("task_type")
            required.add("team_id")

        else:
            raise ChangeGroundingError(
                f"Ændringstypen '{change_type}' kan ikke groundes."
            )

        return required

    def _contains_quote(
        self,
        source_text: str,
        quote: str,
    ) -> bool:
        """
        Sammenligner tolerant over for store bogstaver, tegnsætning
        og gentagne mellemrum.
        """

        normalized_source = self._normalize_text(
            source_text
        )

        normalized_quote = self._normalize_text(
            quote
        )

        if not normalized_quote:
            return False

        return normalized_quote in normalized_source

    def _normalize_text(
        self,
        value: Any,
    ) -> str:
        text = str(
            value or ""
        ).casefold()

        text = text.replace(
            "_",
            " ",
        )

        text = re.sub(
            r"[^\wæøå]+",
            " ",
            text,
            flags=re.UNICODE,
        )

        return " ".join(
            text.split()
        )


scenario_change_grounder = (
    ScenarioChangeGrounder()
)


def ground_changes(
    *,
    question: str,
    changes: list[dict[str, Any]],
    conversation_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Praktisk funktionsindgang til grounding-laget.
    """

    return scenario_change_grounder.ground_changes(
        question=question,
        changes=changes,
        conversation_context=conversation_context,
    )
