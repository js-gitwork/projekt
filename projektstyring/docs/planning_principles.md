# Planning Principles

Dette dokument beskriver de grundlæggende principper for projektstyringssystemet.
Principperne beskriver virksomhedens arbejdsproces og danner grundlag for både
planmotoren og Roerbot.

---

# Projektets livscyklus

Et projekt gennemløber følgende faser:

1. Survey (opmåling)
2. Upcoming (planlægning)
3. Active (udførelse)
4. Completed (afsluttet)

## Survey

Projektet er oprettet.

Opmålingen gennemføres.

Der indsamles oplysninger om:

- installationer
- stik
- dimensioner
- længder
- særlige forhold
- noter

Survey er en projektfase.

Survey er **ikke** en planlagt aktivitet.

Der reserveres ingen ressourcer til survey.

---

## Survey-data

Survey er projektets opmålings- og informationsfase.

Survey gemmes som projektdata, ikke som en planaktivitet.

Alle projekter skal have et `survey`-objekt.

Hvis et gammelt projekt mangler `survey`, oprettes en standardstruktur automatisk, når projektet indlæses.

Survey indeholder som minimum:

- status
- planlagt opmålingsdato
- afsluttet opmålingsdato
- ansvarlig
- noter
- opmålingsdata

Survey må bruges af Roerbot til at vurdere, om projektet er klar til planlægning.

Survey må ikke optage ressourcer i produktionsplanen.

## Upcoming

Projektet er klar til planlægning.

Planen må ændres frit.

Roerbot må:

- ændre startdatoer
- flytte aktiviteter
- skifte hold
- simulere scenarier
- optimere planen

Der findes endnu ingen baseline.

---

## Active

Projektet er sat i gang.

Når status ændres til Active:

- den aktuelle plan gemmes som baseline
- planmotoren fortsætter med at optimere den aktuelle plan
- faktisk udført arbejde registreres
- afvigelser beregnes i forhold til baseline

Planen må stadig ændres.

Baseline ændres aldrig.

---

## Completed

Projektet er afsluttet.

Baseline, faktisk udførelse og afvigelser bevares som historik.

---

# Planlægningsprincipper

Planmotoren planlægger ud fra virksomhedens flaskehalse.

Den primære flaskehals er hovedledningsholdene.

Andre aktiviteter planlægges omkring disse.

---

## Forarbejde

Forarbejde skal være afsluttet før hovedledning.

Der er ingen maksimal afstand mellem forarbejde og hovedledning.

Motoren må placere forarbejdet tidligere, hvis det giver en bedre samlet plan.

---

## Hovedledning

Hovedledningen er den styrende aktivitet.

Resten af planen bygges op omkring hovedledningens dato.

---

## Afhængigheder

Afhængigheder beskriver logiske krav.

Eksempel:

Forarbejde
→ Hovedledning
→ Stikforberedelse
→ Stik
→ Kontrol
→ Korthat
→ Brønd

Virkeligheden kan afvige fra planen.

Planmotoren må ikke skjule afvigelser.

Roerbot skal kunne forklare dem.

---

# Grundprincip

Systemet modellerer virksomhedens arbejdsproces.

Systemet modellerer ikke en teoretisk projektmodel.

Virkeligheden har altid forrang frem for planen.

Roerbot skal hjælpe projektlederen med at forstå konsekvenserne af ændringer – ikke blot registrere dem.

## Datamodel-princip

Hver central datamodel skal have én kilde til standardstruktur.

Eksempel:

`survey_model.py` definerer standardstrukturen for survey.

Andre dele af systemet må bruge modellen, men må ikke kopiere dens struktur manuelt.