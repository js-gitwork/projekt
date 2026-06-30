# Projektstyring – Domænemodel

## Formål

Dette dokument beskriver virksomhedens faglige verden.

Det er fundamentet for hele Projektstyring og skal sikre, at både mennesker, Python og AI anvender de samme definitioner.

Alle øvrige dokumenter bygger oven på dette dokument.

---

# Ansvarsområde

Dette dokument beskriver:

- virksomhedens begreber
- planlægningsobjekter
- relationer mellem objekter
- faglige definitioner

Dette dokument beskriver ikke implementering eller kode.

---

# Grundprincip

Projektstyring modellerer virksomhedens virkelighed.

Systemet skal afspejle den måde virksomheden arbejder på.

Hvis virkeligheden ændrer sig, skal domænemodellen ændres før koden.

---

# Centrale objekter

## Projekt

Et projekt repræsenterer en samlet entreprise.

Et projekt består af:

- kunde
- by
- startdato
- installationer
- holdtildelinger
- plan
- status

Et projekt er den overordnede planlægningsenhed.

---

## Installation

En installation er den mindste planlægningsenhed.

En installation kan indeholde:

- hovedledning
- stikforberedelse
- stik
- kontrol
- korthat
- brøndarbejde

Alle aktiviteter planlægges på installationsniveau.

---

## Aktivitet

En aktivitet er et konkret stykke arbejde.

Eksempler:

- Forarbejde
- Hovedledning
- Stikforberedelse
- Stik
- Kontrol
- Korthat
- Brønd

Aktiviteter har:

- varighed
- rækkefølge
- hold
- startdato
- slutdato

---

## Hold

Et hold udfører aktiviteter.

Et hold har blandt andet:

- kompetencer
- kalender
- kapacitet
- geografisk placering
- planlagte aktiviteter

Et hold kan arbejde på flere projekter.

---

## Kalender

Kalenderen beskriver hvornår et hold arbejder.

Kalenderen indeholder:

- arbejdsdage
- helligdage
- ferie
- særlige arbejdstider

---

# Faglige begreber

## Stik

Stik anvendes ofte synonymt med langhat.

Stikarbejde udføres af opgaven "Stik".

---

## Langhat

Langhat er den normale renovering af et stik.

I daglig tale anvendes "stik" og "langhat" ofte som samme begreb.

---

## Stikåbning

Stikåbning er ikke det samme som stikarbejde.

Stikåbning udføres af samme hold som hovedledningen.

---

## Stikforberedelse

Stikforberedelse er en selvstændig aktivitet.

Den må ikke forveksles med hverken stik eller stikåbning.

---

## Korthat

Korthatte udføres af aktiviteten "Korthat".

En installation kan indeholde både langhatte og ekstra korthatte.

---

## TV

TV anvendes om TV-inspektion.

Begrebet anvendes ofte synonymt med færdig-TV.

---

## KS

KS anvendes ofte om kvalitetskontrol eller færdig-TV.

---

## DS437

DS437 er en metode til brøndrenovering.

---

## Totalrenovering

En større brøndrenovering end DS437.

---

# Planlægningsprincipper

Projektstyring planlægger altid aktiviteter i korrekt rækkefølge.

Grundrækkefølgen er:

1. Forarbejde
2. Hovedledning
3. Stikforberedelse
4. Stik
5. Kontrol
6. Korthat
7. Brønd

Denne rækkefølge er virksomhedens standard.

---

# Fremtidige udvidelser

Domænemodellen forventes senere udvidet med:

- Geografi
- Maskiner
- Materiel
- Køretøjer
- Kompetenceprofiler
- Økonomi
- Kundeaftaler
- Risikovurdering

---

# Designprincip

Domænemodellen er virksomhedens sandhed.

Koden skal tilpasses domænet.

Domænet må aldrig tilpasses koden.
