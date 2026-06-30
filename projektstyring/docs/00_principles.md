# Projektstyring – Grundprincipper

## Formål

Dette dokument beskriver de grundlæggende principper, som styrer udviklingen af Projektstyring.

Hvis en ny funktion eller en ny arkitekturbeslutning er i konflikt med disse principper, skal principperne have forrang.

Projektets succes måles ikke på antallet af funktioner, men på hvor godt systemet hjælper projektledelsen med at træffe bedre beslutninger.

---

# 1. Domænet bestemmer koden

Virksomhedens virkelighed kommer før implementeringen.

Koden skal tilpasses domænet.

Domænet må aldrig ændres for at passe til koden.

---

# 2. Data er sandheden

Projektdata har én autoritativ kilde.

Repositories og databasen repræsenterer den objektive sandhed.

AI må aldrig opfinde projektdata.

---

# 3. Python beregner

Alle objektive beregninger udføres af Python.

Eksempler:

- kapacitet
- konflikter
- planlægning
- spildtid
- belastning
- transport

AI må aldrig gætte disse værdier.

---

# 4. AI analyserer

AI's opgave er at:

- forstå spørgsmål
- vælge relevante data
- analysere konsekvenser
- forklare resultater
- foreslå alternativer

AI er rådgiver.

AI er ikke sandhedskilde.

---

# 5. Alle ændringer simuleres

Ingen ændringer foretages direkte.

Alle ændringer gennemføres først som et scenario.

Scenarioet analyseres.

Konsekvenserne præsenteres.

Brugeren godkender.

Først derefter gemmes ændringen.

---

# 6. Systemet optimerer virksomheden

Projektstyring optimerer ikke ét projekt.

Projektstyring optimerer hele virksomheden.

Der tages blandt andet hensyn til:

- kapacitet
- geografi
- transport
- spildtid
- økonomi
- ressourcer
- kundeaftaler
- risiko

---

# 7. Beslutningsstøtte

Projektstyring skal fungere som virksomhedens digitale projektchef.

Systemet skal hjælpe projektledelsen med at forstå konsekvenserne af en beslutning.

Den endelige beslutning træffes altid af et menneske.

---

# 8. Beslutninger før funktioner

Ingen ny funktion implementeres, før vi kan forklare:

"Hvilken beslutning hjælper denne funktion projektlederen med at træffe?"

Hvis spørgsmålet ikke kan besvares, skal funktionen genovervejes.

---

# 9. Simpel arkitektur

Systemet opdeles i tydelige ansvarsområder.

Repositories leverer data.

Planner beregner planer.

Decision Engine analyserer scenarier.

Roerbot kommunikerer med brugeren.

Ingen komponent må overtage en anden komponents ansvar.

---

# 10. Dokumentationen er en del af systemet

Dokumentationen har samme betydning som kildekoden.

Alle større arkitekturændringer skal opdateres i dokumentationen.

Dokumentationen beskriver systemets intention.

Koden implementerer intentionen.

---

# 11. Ingen overraskelser

Projektstyring skal reducere usikkerhed.

Systemet skal gøre konsekvenser synlige, før de opstår.

Projektledelsen skal kunne se:

- konflikter
- spildtid
- kapacitetsproblemer
- geografiske udfordringer
- økonomiske konsekvenser
- risici

før ændringer gennemføres.

Roerbot skal hjælpe projektledelsen med at træffe beslutninger på et oplyst grundlag.

---

# Projektets løfte

Projektstyring skal ikke blot hjælpe med at lave planer.

Projektstyring skal hjælpe mennesker med at træffe bedre beslutninger.

Roerbot er virksomhedens digitale projektchef.

Roerbot skal kunne simulere, analysere og forklare konsekvenserne af ændringer, før de gennemføres.

Målet er ikke at erstatte projektlederen.

Målet er at give projektlederen det bedst mulige beslutningsgrundlag.
