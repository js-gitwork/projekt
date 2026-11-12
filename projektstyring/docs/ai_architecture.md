
# Rørbot – AI-arkitektur

## Status

Dette dokument beskriver den besluttede målarkitektur for Rørbots AI.

Målarkitekturen er endnu ikke fuldt implementeret.

Autoritative overordnede principper:
- 00_principles.md
- planning_principles.md

Ved konflikt har 00_principles.md forrang.

## 1. Formål

Rørbot er VP Villy Poulsen A/S' intelligente brugergrænseflade
til projektstyring, dataundersøgelse og beslutningsstøtte.

Systemet skal kunne vedligeholdes og videreudvikles af andre
end den oprindelige udvikler.

AI-modeller og ERP-systemer skal kunne udskiftes uden at
omskrive virksomhedens domænelogik.

## 2. Agentarkitektur

Rørbot har én brugerrettet samtale og fælles dialogkontekst.

To logiske specialistroller:

Undersøgeren:
- Undersøger autoriserede datakilder.
- Opdager skemaer og relationer.
- Sammenholder registreringer.
- Finder afvigelser og manglende oplysninger.
- Dokumenterer kilder og usikkerheder.
- Har ikke ret til at ændre produktionsdata.

Planlæggeren:
- Anvender eksisterende domæneservices.
- Undersøger kapacitet og afhængigheder.
- Opretter og sammenligner scenarier.
- Præsenterer konsekvenser.
- Anmoder om eksplicit menneskelig godkendelse.
- Gennemfører kun ændringer gennem den autoritative
  ændrings- og transaktionspipeline.

Rollerne må dele oplysninger, men må ikke oprette
parallelle implementeringer af domænefunktioner.

## 3. AI-gateway

Alle nye AI-agenter kommunikerer gennem en fælles gateway.

Gatewayen skal isolere:
- AI-leverandør og endpoint
- modelnavn og konfiguration
- beskedformater
- native tool calling
- håndtering af leverandørforskelle
- fejl og timeouts

Mål:
- Mistral EU API
- lokale OpenAI-kompatible modeller
- fremtidige modelleverandører

API-kompatibilitet garanterer ikke ens modeladfærd.
En ny model skal bestå de relevante accepttests.

## 4. Datakilder og datakatalog

Datakilder tilgås gennem godkendte dataadaptere,
repositories og services.

Datakataloget skal kunne registrere:
- datakildens identitet og type
- tabeller og kolonner
- datatyper
- verificerede relationer
- forretningsmæssige feltbetydninger
- dokumentation og verificeringsstatus
- tidspunkt og metode for verificering

AI må foreslå relationer og feltbetydninger.

Forslag er ikke automatisk verificerede fakta.

Datakataloget må ikke blive en alternativ
projektdatabase eller en skjult source of truth.

## 5. Autoritative data og eksterne undersøgelser

Projektstyrings domænedatabase er autoritativ for
systemets gældende projekt- og planlægningsdata.

Eksterne systemer kan have autoritative registreringer
inden for deres egne ansvarsområder.

Undersøgeren må foretage autoriserede read-only
undersøgelser direkte i eksterne kilder.

Disse undersøgelser må ikke:
- overskrive gældende projektdata
- ændre planer eller aktiviteter
- omgå repository- og servicelaget
- omgå importens afvigelsesbehandling
- omgå godkendelsesprocessen

Uoverensstemmelser mellem kilder skal synliggøres.

## 6. Sikkerhed

Adgang til data skal følge den autentificerede brugers
rettigheder, ikke alene AI-modellens instruktioner.

Databaseværktøjer skal håndhæve:
- læse-/skriverettigheder
- adgang til tilladte datakilder
- relevante bruger- og databegrænsninger
- validering af forespørgsler
- begrænsning af datamængder og tidsforbrug

Databasetekst behandles som data, ikke som
instruktioner til AI-agenten.

Ændringer kræver eksisterende godkendelsesworkflow.

## 7. Korrekthed og kontrol

Native function calling er en kommunikationsmekanisme,
ikke en garanti for korrekte resultater.

Objektive beregninger og sammenkoblinger udføres
deterministisk i Python eller gennem godkendte
databasetjenester.

Resultatkontrol skal omfatte:
- dokumenteret datakilde
- korrekt relation mellem datasæt
- fuldstændig dataindlæsning
- korrekt forretningsmæssig feltbetydning
- antal og summeringer, hvor relevant
- tydelig håndtering af manglende data

Manglende oplysninger må ikke præsenteres som nul.

## 8. Legacy-migration

Den tidligere JSON-intentbaserede fortolker og
rapportpipeline skal undersøges og erstattes af
den nye generiske agentarkitektur.

Eksisterende domæneservices skal genbruges, når
de følger 00_principles.md.

Legacy-funktioner skal ikke bevares alene af hensyn
til bagudkompatibilitet.

Migrationen gennemføres kontrolleret:
1. Identificér eksisterende ansvar og afhængigheder.
2. Implementér den nye generiske funktion.
3. Verificér funktionalitet og sikkerhed.
4. Flyt den aktive produktionsvej.
5. Fjern forladte routes, imports, kode og tests.
6. Opdatér dokumentationen.

En parallel løsning må kun eksistere i en afgrænset
migrationsperiode og må ikke give skjult fallback.

## 9. Implementeringsstatus – 2026-11-12

Afprøvet:
- Native function calling med Mistral.
- Dynamisk kolonneopslag i udvalgte C5-tabeller.
- Read-only projektdataopslag.
- Sammenkobling af data via valgte relationsfelter.
- Separat AI-gateway med eksisterende Mistral-klient.

Endnu ikke færdigt:
- Modeluafhængig normalisering af værktøjskald.
- Fuldstændigt dynamisk datakatalog.
- Vedvarende verificering af feltbetydninger.
- Uafhængig kontrol af alle AI-svar.
- Brugerbaseret autorisation for alle agentværktøjer.
- Integration af begge roller i den aktive Rørbot.
- Endelig udfasning og fjernelse af legacy.

Pilotfiler er testkode og må ikke betragtes som
færdige produktionskomponenter.

## 10. Vedligeholdelse og overdragelse

Ved ændringer skal udvikleren:
- dokumentere modulets ansvar og grænseflader
- forklare væsentlige designvalg
- dokumentere sikkerhedsforudsætninger
- opdatere relevante tests
- opdatere den autoritative dokumentation
- fjerne dokumentation for forladt arkitektur

docs/ beskriver den aktuelle arkitektur og tydeligt
markerede mål, der endnu ikke er implementeret.

Git bevarer historikken.
