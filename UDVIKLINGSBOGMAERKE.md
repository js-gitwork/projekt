# Rørbot – udviklingsbogmærke 2026-10-29

STATUS
- C5-synkronisering fungerer: 1376 rækker, 0 ændringer ved gentagen kontrol.
- Ændringsjournal fungerer med schema_enrichment.
- Langhatlængde: ETPROKONPOST.RENOVLNG er implementeret.
- Hovedledning fakturering: NYLEDTVLXNGDE og NYLEDDIM er fundet, men endnu ikke importeret.
- Faktisk hovedledningslængde: ETPROKONINST.INSTALLNG er kandidat, ikke endeligt verificeret.

NÆSTE OPGAVE – KUN DENNE
Find SQL-kilden til Type i C5 projektoversigt.
Skeln sikkert mellem Strømpe Filt og Stramforing.
Brug V164470 Struer som sammenligningsprojekt.
Gæt ikke ud fra INSTEJER, FILTINST eller INSTTYPE.

EFTERFØLGENDE
1. Udvid reader.py med verificerede faktureringsfelter.
2. Test preview, apply og journal.
3. Byg produktionsrapport pr. dato, dimension og foringstype.

SIKKERHEDSNÅLE
- Manglende faktisk installationslængde på hovedledning/langhat.
- Backendfejl på relining-forespørgsel for V166620 og V166660.
- Periodisk C5-synkronisering.
- Administrativ projektlukning.
- Månedlig afregningsrapport 15.-14.
