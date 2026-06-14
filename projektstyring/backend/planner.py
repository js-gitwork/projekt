from datetime import date, timedelta
from .models import Aktivitet, Installation, Aktivitetstype, PROCESS_FLOW


# =========================
# 1. HOLD-MAPPING (midlertidig)
# =========================
# Her kan vi senere koble database / konfiguration på
DEFAULT_HOLD_MAP = {
    Aktivitetstype.FORARBEJDE: "tv_cutter",
    Aktivitetstype.HOVEDLEDNING: "hoved_stramforing",
    Aktivitetstype.STIK_FORBEREDELSE: "tv_stik",
    Aktivitetstype.STIK: "langhat",
    Aktivitetstype.KONTROL: "tv_kontrol",
    Aktivitetstype.KORTHAT: "korthat_hold",
    Aktivitetstype.BRØND: "brøndhold",
}


# =========================
# 2. STANDARD VARIGHEDER (kan senere erstattes af AI)
# =========================
DEFAULT_VARIGHED = {
    Aktivitetstype.FORARBEJDE: 1.0,
    Aktivitetstype.HOVEDLEDNING: 2.0,
    Aktivitetstype.STIK_FORBEREDELSE: 0.5,
    Aktivitetstype.STIK: 2.0,
    Aktivitetstype.KONTROL: 0.5,
    Aktivitetstype.KORTHAT: 1.0,
    Aktivitetstype.BRØND: 1.0,
}


# =========================
# 3. GENERER AKTIVITETER
# =========================
def generer_aktiviteter(installation: Installation) -> Installation:
    """
    Opretter aktiviteter i korrekt procesrækkefølge
    """

    aktiviteter = []

    for idx, type_ in enumerate(PROCESS_FLOW):

        aktivitet = Aktivitet(
            id=f"{installation.id}_{type_}",
            type=type_,
            hold=DEFAULT_HOLD_MAP.get(type_, "ukendt"),
            installation_id=installation.id,
            varighed_dage=DEFAULT_VARIGHED.get(type_, 1.0),
        )

        # afhængighed = forrige step
        if idx > 0:
            aktivitet.afhænger_af.append(
                f"{installation.id}_{PROCESS_FLOW[idx - 1]}"
            )

        aktiviteter.append(aktivitet)

    installation.aktiviteter = aktiviteter
    return installation


# =========================
# 4. DEBUG OUTPUT
# =========================
def print_plan(installation: Installation):
    print(f"\n📦 Installation {installation.id}")
    print("-" * 40)

    for a in installation.aktiviteter:
        print(f"{a.type:20} | hold: {a.hold} | varighed: {a.varighed_dage}d")

        if a.afhænger_af:
            print(f"   ↳ afhænger af: {a.afhænger_af[0]}")
