# Projektstyring – Arkitektur

## Formål

Dette dokument beskriver systemets overordnede arkitektur.

Arkitekturen opdeler systemet i tydelige ansvarsområder, så hver komponent har ét veldefineret ansvar.

Ingen komponent må overtage en anden komponents ansvar.

Dette dokument beskriver principperne bag systemet og ikke den konkrete implementering.

---

# Arkitekturens lag

Projektstyring består af fem hovedlag.

```
                    Bruger
                       │
                       ▼
                  Roerbot (AI)
                       │
                       ▼
               Decision Engine
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
     Planner     Capacity Engine   Simulation
        │              │              │
        └──────────────┼──────────────┘
                       ▼
               Project Repository
                       │
                       ▼
                   Database
```

Alle komponenter har ét ansvar.

---

# Lag 1 – Data

## Ansvar

Systemets data udgør den objektive sandhed.

Data må aldrig opfindes eller beregnes af AI.

Eksempler:

- projekter
- installationer
- hold
- kalendere
- kapaciteter
- kunder
- geografi

## Komponenter

- Database
- Repository-klasser

Repository-laget er den eneste adgang til data.

---

# Lag 2 – Beregning

Dette lag udfører alle objektive beregninger.

## Planner

Planner beregner projektplaner.

Planner kender blandt andet:

- aktivitetsrækkefølge
- varigheder
- afhængigheder
- kalenderregler

Planner træffer ingen beslutninger.

Planner udfører beregninger.

---

## Capacity Engine

Capacity Engine beregner:

- kapacitet
- belastning
- ledig tid
- arbejdsdage
- ferie
- kalenderbegrænsninger

Capacity Engine arbejder udelukkende med ressourcer.

---

## Simulation

Simulation udfører ændringer på kopier af data.

Simulation ændrer aldrig virkeligheden.

Simulation kan eksempelvis:

- flytte projekter
- flytte aktiviteter
- flytte hold
- ændre startdatoer

Alle ændringer udføres på en kopi.

---

# Lag 3 – Decision Engine

Decision Engine er systemets centrale analysemotor.

Decision Engine udfører ikke planlægning.

Decision Engine analyserer planlægningen.

Den kan blandt andet:

- simulere scenarier
- sammenligne planer
- opdage konflikter
- beregne konsekvenser
- analysere kapacitet
- analysere transport
- analysere økonomi
- finde alternative løsninger

Decision Engine leverer analyser.

Den træffer ikke beslutninger.

---

# Lag 4 – AI

Roerbot udgør systemets AI-lag.

Roerbot anvender Decision Engine og de øvrige komponenter.

Roerbot må:

- forstå spørgsmål
- vælge relevante analyser
- forklare resultater
- foreslå løsninger
- argumentere for anbefalinger

Roerbot må aldrig:

- opfinde data
- ændre planer
- beregne kapacitet
- gætte konflikter

---

# Lag 5 – Brugergrænseflade

Brugergrænsefladen viser systemets data.

Den skal gøre det let at:

- planlægge
- analysere
- simulere
- sammenligne
- godkende ændringer

Brugergrænsefladen må aldrig indeholde forretningslogik.

---

# Dataflow

Systemets normale dataflow er:

```
Bruger

↓

Roerbot

↓

Decision Engine

↓

Planner / Capacity Engine

↓

Repository

↓

Database
```

Resultatet sendes tilbage gennem samme kæde.

---

# Simulation

Alle ændringer følger samme proces.

```
Virkelighed

↓

Kopi

↓

Ændring

↓

Ny plan

↓

Analyse

↓

Anbefaling

↓

Godkendelse

↓

Gem
```

Hvis brugeren afviser ændringen, slettes scenariet.

Virkeligheden påvirkes ikke.

---

# Ansvarsfordeling

| Komponent | Ansvar |
|-----------|---------|
| Database | Permanent lagring |
| Repository | Dataadgang |
| Planner | Planberegning |
| Capacity Engine | Ressourceberegning |
| Simulation | Midlertidige scenarier |
| Decision Engine | Analyse og konsekvensberegning |
| Roerbot | Kommunikation og rådgivning |
| Bruger | Beslutninger |

---

# Arkitekturprincipper

Hver komponent har ét ansvar.

Komponenter kommunikerer gennem veldefinerede grænseflader.

Ingen komponent må kende interne detaljer om andre komponenter.

Alle analyser skal kunne udføres uden AI.

AI er en klient til systemet.

Det betyder, at systemet senere kan anvendes af:

- webgrænsefladen
- mobilapp
- API
- automatiske rapporter
- andre AI-modeller

uden at ændre den underliggende arkitektur.

---

# Fremtidig arkitektur

Systemet forventes senere udvidet med:

- geografisk analyse
- økonomimotor
- scenariehistorik
- optimeringsmotor
- maskinplanlægning
- materielplanlægning
- prognosemodeller
- BI-integration

Disse komponenter skal integreres som selvstændige moduler uden at ændre de eksisterende ansvarsområder.

---

# Arkitekturens mål

Arkitekturen skal sikre:

- tydelige ansvarsområder
- høj testbarhed
- enkel vedligeholdelse
- let udvidelse
- høj datakvalitet
- reproducerbare analyser

Systemet skal kunne vokse i funktionalitet uden at miste sin struktur.

Arkitekturen skal gøre det muligt at udvikle nye funktioner uden at skabe teknisk gæld.
