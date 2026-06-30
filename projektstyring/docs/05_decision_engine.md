# Projektstyring – Decision Engine

## Formål

Decision Engine er Projektstyrings centrale beslutningsmotor.

Motorens opgave er at analysere konsekvenserne af ændringer, før de gennemføres.

Decision Engine ændrer aldrig virkeligheden.

Motoren arbejder udelukkende med simuleringer.

---

# Ansvarsområde

Decision Engine har ansvar for:

- simulering
- konsekvensanalyse
- konfliktdetektion
- sammenligning af scenarier
- anbefalinger
- optimeringsgrundlag

Decision Engine har ikke ansvar for:

- lagring
- brugergrænseflade
- AI-dialog
- planberegning

---

# Grundprincip

Alle beslutninger behandles som scenarier.

Et scenarie er en kopi af virkeligheden, hvor én eller flere ændringer er foretaget.

Scenariet analyseres.

Resultatet præsenteres.

Brugeren beslutter.

---

# Workflow

Alle analyser følger samme proces.

```
Virkelighed

↓

Kopi

↓

Ændringer

↓

Planning Engine

↓

Analyse

↓

Sammenligning

↓

Anbefaling

↓

Bruger

↓

Gem eller forkast
```

Ingen data ændres under analysen.

---

# Scenario

Et scenario består af:

- identifikation
- beskrivelse
- ændringer
- analyser
- anbefalinger

Eksempel:

```
Scenario

Flyt V165460

Fra:
29-06-2026

Til:
06-07-2026
```

---

# Typer af ændringer

Decision Engine skal kunne håndtere blandt andet:

- ændring af projektstart
- flytning af aktiviteter
- ændring af hold
- ændring af kalender
- ændring af kapacitet
- ændring af ressourcer

Alle ændringer skal kunne kombineres.

---

# Analyse

Motoren analyserer blandt andet:

- påvirkede projekter
- påvirkede hold
- ændrede aktiviteter
- ændret kapacitetsforbrug
- ventetid
- spildtid
- transport
- kalenderkonflikter
- dobbeltbookinger
- forsinkelser

---

# Konflikter

Decision Engine identificerer konflikter.

Eksempler:

- dobbeltbooket hold
- manglende kapacitet
- manglende kalender
- manglende kompetencer
- afhængigheder som brydes

Motoren løser ikke konflikterne.

Motoren beskriver dem.

---

# Anbefalinger

Decision Engine skal kunne foreslå alternativer.

Eksempel:

Alternativ A

Behold TV22.

Transport:
40 km

Spildtid:
2 dage

---

Alternativ B

Flyt TV11.

Transport:
15 km

Spildtid:
0 dage

---

Alternativ C

Udskyd projekt.

Transport:
0 km

Forsinkelse:
5 dage

Motoren leverer fakta.

Roerbot forklarer anbefalingerne.

---

# Geografi

Geografi er en del af beslutningsgrundlaget.

Motoren skal blandt andet kunne analysere:

- afstand
- køretid
- region
- kundeområde

Et ledigt hold er ikke nødvendigvis det bedste hold.

---

# Økonomi

Decision Engine skal på sigt kunne beregne:

- transportomkostninger
- hotelovernatninger
- ventetid
- tabt produktion
- maskinomkostninger
- samlet projektøkonomi

Økonomi anvendes som beslutningsgrundlag.

---

# Porteføljeoptimering

Decision Engine analyserer hele virksomheden.

Motoren optimerer ikke ét projekt.

Motoren optimerer den samlede produktion.

En ændring kan derfor påvirke flere projekter samtidigt.

---

# Samarbejde med Roerbot

Decision Engine leverer analyser.

Roerbot omsætter analyserne til naturligt sprog.

Eksempel:

Bruger:

> Flyt Herslev en uge.

Decision Engine:

- analyserer
- finder konflikter
- beregner konsekvenser
- finder alternativer

Roerbot:

forklarer resultatet.

---

# Samarbejde med Planning Engine

Decision Engine udfører ingen planlægning.

Motoren ændrer input.

Kalder Planning Engine.

Modtager en ny plan.

Sammenligner den med den oprindelige.

---

# Fremtidige udvidelser

Decision Engine forventes senere udvidet med:

- AI-optimering
- automatisk scenariegenerering
- risikovurdering
- økonomiske prognoser
- maskinlæring
- erfaring fra tidligere projekter

---

# Designprincip

Decision Engine er virksomhedens analytiske hjerne.

Planning Engine beregner.

Decision Engine analyserer.

Roerbot kommunikerer.

Brugeren beslutter.

Virkeligheden ændres først efter godkendelse.
