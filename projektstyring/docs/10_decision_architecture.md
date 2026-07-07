# 10. Decision Architecture

## Formål

Projektstyring er ikke et automatisk planlægningssystem.

Systemets formål er at fungere som digital projektleder og beslutningsstøtte.

Roerbot må derfor aldrig selv træffe projektmæssige beslutninger.

Roerbot skal:

- forstå projektlederens intention
- indsamle relevante fakta
- analysere konsekvenser
- simulere ændringer
- forklare konsekvenserne
- foreslå løsninger

Projektlederen træffer beslutningen.

---

# Grundprincip

Der skelnes mellem:

- fakta
- regler
- beslutninger

## Fakta

Eksempler:

- antal stik
- længder
- brønde
- hold
- kalendere
- kapaciteter

Fakta beskriver virkeligheden.

---

## Regler

Regler beskriver virksomhedens normale arbejdsgang.

Eksempel:

Forarbejde
↓
Hovedledning
↓
Stikforberedelse
↓
Stik
↓
Kontrol
↓
Korthat
↓
Brønd
↓
DTVK

Regler gælder som udgangspunkt altid.

---

## Beslutninger

Projektledelsen kan vælge at fravige reglerne.

Eksempler:

- arbejde i ferie
- lørdagsarbejde
- ekstra kapacitet
- langhat før hovedledning
- flytte hold mellem projekter
- udsætte DTVK
- springe aktiviteter over

Beslutninger skal:

- begrundes
- analyseres
- godkendes
- dokumenteres

---

# Arkitektur

Roerbot arbejder i følgende lag:

Conversation Engine
↓

Conversation Resolver
↓

Decision Engine
↓

Project Rule Resolver
↓

Project Planner
↓

MultiScheduleEngine
↓

CapacityEngine

Hvert lag har ét ansvar.

---

# Decision Engine

Decision Engine analyserer konsekvenserne af en ønsket ændring.

Eksempel:

"Alle langhatte skal være færdige i uge 31."

Decision Engine skal:

- identificere hvilke regler der brydes
- simulere konsekvenser
- finde konflikter
- beregne ny plan
- præsentere resultatet

Decision Engine ændrer aldrig projektet.

---

# Project Rule Resolver

Project Rule Resolver omsætter godkendte beslutninger til projektregler.

Eksempler:

- workflow-undtagelser
- kapacitetsændringer
- kalenderændringer
- projekt-specifikke regler

Planneren arbejder kun med de regler, som resolveren leverer.

---

# Godkendelsesprincip

Ingen projektændringer implementeres automatisk.

Workflow:

Bruger
↓

Roerbot
↓

Analyse
↓

Konsekvensberegning
↓

Projektleder godkender
↓

Projekt opdateres
↓

Snapshot oprettes
↓

Beslutning logges

---

# Snapshot

Før enhver projektændring oprettes et snapshot.

Efter ændringen oprettes et nyt snapshot.

Det gør det muligt at forklare:

- hvad ændrede sig
- hvorfor
- hvornår
- hvem godkendte ændringen

---

# Vision

Roerbot er ikke en chatbot.

Roerbot er en digital projektleder.

Den skal kunne forklare alle sine anbefalinger.

Systemet skal ikke kun kunne beregne en plan.

Det skal kunne forklare, hvorfor planen ser ud som den gør.
