# Projektstyring – Autoritative udviklingsprincipper

## Status

Dette dokument er den autoritative beskrivelse af Projektstyrings
arkitektur og udviklingsprincipper.

Hvis eksisterende kode, tests, dokumentation, JSON-filer eller tidligere
implementeringer er i konflikt med dette dokument, er de legacy.

Legacy skal ikke understøttes af ny kode.

Hvis gammel kode bryder sammen, fordi den ikke følger den aktuelle
arkitektur, skal den enten migreres eller fjernes. Der må ikke indføres
kompatibilitetslag alene for at holde gammel arkitektur i live.

---

# 1. Formål

Projektstyring er et databasebaseret beslutningsstøttesystem til
projektledelse.

Systemets opgave er ikke blot at generere planer.

Det skal hjælpe projektledelsen med at:

- forstå den aktuelle virkelighed
- analysere konsekvenser
- opdage problemer før de opstår
- simulere ændringer
- sammenligne alternativer
- dokumentere beslutninger
- forstå hvorfor planer og projekter har ændret sig

Rørbot er systemets intelligente brugergrænseflade og digitale
projektleder.

Den endelige forretningsmæssige beslutning træffes af et menneske.

---

# 2. Domænet bestemmer systemet

Virksomhedens faktiske arbejdsgange bestemmer domænemodellen.

Domænet må aldrig ændres for at gøre eksisterende kode lettere at
vedligeholde.

Hvis virkeligheden og implementeringen er uenige, skal implementeringen
ændres.

Eksisterende kode er ikke i sig selv et argument for en
arkitekturbeslutning.

---

# 3. Databasen er source of truth

Alle gældende driftsdata skal have én autoritativ kilde:

DATABASE → REPOSITORY → SERVICE

Dette gælder blandt andet:

- projekter
- installationer
- tekniske assets
- brønde
- stræk
- stik
- hold
- kalendere
- kapaciteter
- assignments
- projektregler
- scenarier
- revisioner
- beslutninger
- snapshots
- historik

Produktionskode må ikke vælge mellem database og gamle JSON-data.

Hvis data er migreret til databasen, skal gammel JSON-baseret
dataadgang fjernes.

Manglende databasedata skal give en synlig fejl.

Systemet må ikke stille og roligt falde tilbage til JSON.

---

# 4. JSON er ikke persistent produktionslagring

JSON må anvendes som et eksplicit import- eller eksportformat, hvis der
findes et konkret behov.

JSON må ikke anvendes som:

- alternativ projektdatabase
- fallback for manglende databasedata
- parallel source of truth
- skjult konfiguration af konkrete projekter
- persistent lagring af nye domænefunktioner

Eksisterende JSON-filer fra den tidligere arkitektur skal migreres,
arkiveres eller slettes.

Ny produktionsfunktionalitet må ikke afhænge af dem.

---

# 5. Repository-laget ejer dataadgangen

Vedvarende domænedata tilgås gennem repositories.

Andre komponenter skal ikke:

- læse projekt-JSON direkte
- skrive direkte til gamle projektfiler
- implementere alternative datakilder
- have deres egen skjulte persistence

Repositories repræsenterer adgangen til systemets objektive sandhed.

---

# 6. Python beregner

Objektive beregninger udføres deterministisk af systemets motorer.

Det gælder blandt andet:

- planlægning
- kapacitet
- kalendere
- afhængigheder
- workflow
- konflikter
- belastning
- varigheder
- deadlines
- konsekvenser, der kan beregnes objektivt

AI må ikke gætte disse resultater.

Rørbot kan anmode om beregninger og forklare dem.

---

# 7. Rørbot forstår og kommunikerer

Rørbot er ikke en separat projektstyringsmotor.

Rørbot skal:

- forstå naturligt sprog
- forstå brugerens intention
- finde relevante entiteter
- etablere kontekst
- bede om manglende oplysninger
- anvende systemets services
- forklare fakta og analyser
- foreslå muligheder
- føre en sammenhængende dialog

Rørbot må ikke have parallel forretningslogik til den logik, som
systemets øvrige klienter anvender.

Web-UI, API, Rørbot og fremtidige klienter skal kunne anvende de samme
domæneservices.

---

# 8. AI er ikke sandhedskilde

AI må aldrig opfinde:

- projektdata
- værdier
- relationer
- hold
- datoer
- kapaciteter
- konflikter
- godkendere
- regler
- historik

AI fortolker brugerens intention.

Systemet grounder fortolkningen mod registrerede data.

Hvis grounding ikke kan gennemføres entydigt, skal der spørges eller
returneres en tydelig fejl.

---

# 9. Generisk ændringsarkitektur

En konkret brugerforespørgsel er et eksempel på en domæneoperation.

Den konkrete testcase må aldrig blive arkitekturen.

Eksempel:

"Ret dybden på brønd 4612031 til 2,23 meter"

er en konkret forekomst af en generisk ændring af et felt på en
domæneentitet.

Produktionskode må derfor ikke kende:

- V165460
- 4612031
- 2,23
- Jacob

medmindre værdierne kommer fra brugerinput, database eller anden
autoriseret runtime-kontekst.

Det samme princip gælder alle projekter, installationer, hold,
aktiviteter og øvrige entiteter.

---

# 10. Ingen hardcodede forretningsdata

Produktionskode må ikke hardcode konkrete:

- projekt-id'er
- installations-id'er
- brøndnumre
- hold-id'er
- medarbejdere
- godkendere
- deadlines
- ugenumre
- kundedata
- projektspecifikke undtagelser

Konkrete værdier må eksistere i:

- databasen
- brugerinput
- autoriseret konfiguration
- migrationsdata
- eksplicitte test-fixtures

Hvis en konkret værdi er nødvendig for en produktionsfunktion, skal
dens autoritative kilde kunne forklares.

---

# 11. Ændringer følger én fælles pipeline

Projektændringer skal følge den generiske ændringsarkitektur.

Principielt flow:

BRUGER
  ↓
RØRBOT / ANDEN KLIENT
  ↓
INTERPRETER
  ↓
GROUNDING
  ↓
RESOLVER
  ↓
SCENARIO / CHANGE SET
  ↓
BEREGNING OG KONSEKVENSANALYSE
  ↓
PRÆSENTATION
  ↓
MENNESKELIG GODKENDELSE
  ↓
DECISION / EXECUTION
  ↓
DATABASE
  ↓
HISTORIK / SNAPSHOTS

En ny ændringstype skal integreres i denne arkitektur.

Der må ikke oprettes et separat workflow alene for at håndtere én
bestemt brugerforespørgsel.

---

# 12. Scenarier repræsenterer forslag

Et scenarie ændrer ikke den gældende virkelighed.

Et scenarie kan indeholde:

- ét eller flere projekter
- én eller flere ændringer
- beregnede planer
- konflikter
- advarsler
- konsekvenser
- flere revisioner

Revisioner bevares som historik.

Et afvist forslag skal ikke nødvendigvis slettes.

Historikken skal gøre det muligt at forstå dialogen og udviklingen i
beslutningen.

---

# 13. Godkendelse er eksplicit

Ingen ændring af gældende projektdata må gennemføres uden eksplicit
menneskelig godkendelse.

Rørbot må aldrig antage hvem der godkender.

approved_by er data.

Godkenderen skal komme fra:

- en autoritativ autentificeret brugeridentitet, eller
- en eksplicit oplysning fra brugeren

Hvis identiteten ikke er kendt, skal Rørbot spørge.

Personnavne må aldrig hardcodes som fallback.

---

# 14. Godkendelse og execution er atomisk

En godkendt ændring skal gennemføres som en kontrolleret
databasetransaktion.

Principielt:

VALIDER AKTUEL VIRKELIGHED
↓
SNAPSHOT FØR
↓
DECISION
↓
UDFØR ÆNDRINGER
↓
GENBEREGN / VALIDÉR
↓
SNAPSHOT EFTER
↓
COMMIT

Hvis et nødvendigt trin fejler:

ROLLBACK

Der må ikke efterlades en halv gennemført beslutning.

---

# 15. Historik er en del af domænet

Systemet skal kunne forklare:

- hvad der blev ændret
- hvad værdien var før
- hvad værdien blev efter
- hvorfor ændringen blev foreslået
- hvem der godkendte
- hvornår den blev godkendt
- hvilke konsekvenser der blev beregnet

Historik er ikke debug-information.

Historik er produktdata.

---

# 16. Conversation state er ikke projektdata

Conversation state bruges til at bevare midlertidig dialogkontekst.

Det kan eksempelvis være:

- aktivt scenario_id
- hvilken rapport der tales om
- et afventende spørgsmål
- relevante referencer til domænedata

Conversation state må ikke blive en alternativ database.

Hvis Rørbot skal bruge gældende projektdata, skal de hentes fra den
autoritative datakilde.

---

# 17. Én implementering af hver domænefunktion

Der må ikke eksistere permanente parallelle motorer for samme
domæneoperation.

Hvis en ny generisk implementering erstatter en gammel, skal den gamle
udfases.

Der må ikke bevares gamle implementationsveje "for en sikkerheds
skyld", hvis de kan få produktionssystemet til at anvende den forkerte
arkitektur.

Fail fast er bedre end silent fallback.

---

# 18. Legacy må gerne gå i stykker

Bagudkompatibilitet med forladt udviklingsarkitektur er ikke et mål.

Hvis gammel kode, gamle tests eller gamle datafiler forventer:

- JSON persistence
- hardcodede workflows
- gamle planner-implementeringer
- parallelle repositories
- gamle conversation-routes
- andre forladte arkitekturer

skal produktionskoden ikke ændres for at gøre dem grønne.

De skal migreres eller fjernes.

En tydelig fejl er bedre end et system, der lydløst anvender gammel
arkitektur.

---

# 19. Tests følger produktionsarkitekturen

Tests skal verificere den arkitektur, systemet skal ende med.

Tests må ikke fastholde legacy.

Når en gammel test er i konflikt med den aktuelle domænemodel eller
arkitektur, skal testen omskrives eller slettes.

Konkrete testdata er tilladt i fixtures.

Hardcodede testdata må ikke sive ind i produktionskode.

Målet er ikke:

"Alle gamle tests er grønne."

Målet er:

"Den aktuelle arkitektur er korrekt verificeret."

---

# 20. Dokumentationen beskriver nutiden

Dokumentation er en del af systemet.

Autoritativ dokumentation skal beskrive den arkitektur, der gælder nu.

Historiske arkitekturbeskrivelser må ikke ligge blandt den aktuelle
dokumentation på en måde, hvor de kan forveksles med gældende design.

Historik kan bevares i Git.

Git er arkivet.

docs/ beskriver det aktuelle system.

---

# 21. Ingen midlertidige produktionsløsninger

En midlertidig løsning må ikke indføres i produktionsarkitekturen uden
en eksplicit grund.

Undgå:

- special cases
- fallback til gamle data
- midlertidige hardcodings
- parallelle implementationsveje
- "vi retter det senere"-arkitektur

Hvis den generiske løsning kræver mere arbejde, implementeres den
generiske løsning.

---

# 22. Nye funktioner starter med domænet

Før kode ændres, skal følgende kunne besvares:

1. Hvilken virkelig forretningsfunktion implementerer vi?
2. Hvilke domæneentiteter berøres?
3. Hvor findes den autoritative data?
4. Hvilken eksisterende service ejer funktionen?
5. Skal dette være en generisk operation?
6. Hvordan simuleres konsekvensen?
7. Kræver operationen menneskelig godkendelse?
8. Hvordan registreres historikken?

Først derefter implementeres løsningen.

---

# 23. Før eksisterende kode genbruges

At kode allerede findes betyder ikke, at den skal bruges.

Før en eksisterende komponent bygges videre på, skal det vurderes om
den tilhører den aktuelle arkitektur.

Hvis ikke, skal den ikke bringes tilbage til live alene fordi den er
tilgængelig.

---

# 24. Oprydning er en del af migrationen

Når en ny arkitektur overtager et område, afsluttes arbejdet med at
identificere:

- gammel produktionskode
- gamle imports
- gamle routes
- gamle repositories
- gamle JSON-afhængigheder
- gamle tests
- gamle dokumenter

Disse migreres, arkiveres eller slettes.

En migration er ikke færdig, mens den gamle produktionsvej stadig kan
aktiveres ved et uheld.

---

# 25. Udviklingsregel

Når valget står mellem:

A. at få en eksisterende testcase til at virke ved hjælp af en
specialløsning

eller

B. at implementere den korrekte generiske domænefunktion

vælges B.

Når valget står mellem:

A. silent fallback til gammel arkitektur

eller

B. en tydelig fejl

vælges B.

Når valget står mellem:

A. at bevare gammel kode fordi den måske stadig bruges

eller

B. først at undersøge dens faktiske rolle og derefter fjerne den hvis
den er legacy

vælges B.

---

# Projektets arkitekturløfte

DATA ER SANDHEDEN.

PYTHON BEREGNER.

AI FORSTÅR, ANALYSERER OG FORKLARER.

SCENARIER VISER KONSEKVENSER FØR ÆNDRINGER.

MENNESKET BESLUTTER.

DATABASETRANSAKTIONEN ÆNDRER VIRKELIGHEDEN.

HISTORIKKEN FORKLARER HVAD DER SKETE.

LEGACY FÅR IKKE LOV TIL AT BESTEMME FREMTIDENS ARKITEKTUR.
