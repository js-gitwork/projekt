# Planning Principles

## Status

Dette dokument beskriver de aktuelle domæneprincipper for
projektets livscyklus og produktionsplanlægning.

De overordnede arkitektur- og udviklingsprincipper findes i
`00_principles.md`.

Hvis dette dokument og `00_principles.md` er i konflikt,
har `00_principles.md` forrang.

---

# 1. Projektets livscyklus

Et projekt gennemløber overordnet følgende faser:

1. Survey
2. Upcoming
3. Active
4. Completed

Status beskriver projektets aktuelle forretningsmæssige fase.

Status må ikke bruges som erstatning for registrerede fakta om
produktion, opmåling eller plan.

---

# 2. Survey

Survey er projektets opmålings- og afklaringsfase.

Survey er ikke en produktionsaktivitet og reserverer derfor ikke
produktionsressourcer i planmotoren.

Et projekt kan allerede eksistere i systemet, før survey er afsluttet.

I den normale arbejdsgang oprettes projektet i C5, hvorefter
opmålingsdata fra C5 importeres til Projektstyring.

Survey-data kan blandt andet beskrive:

- installationer
- brøndstræk
- brønde
- eksisterende dimensioner
- nye dimensioner
- eksisterende længder
- nye længder
- dybder
- profiler
- materialer
- trafikforhold
- bemærkninger
- hvem der har udført opmålingen

Survey beriger og korrigerer de tekniske data, som systemet allerede
kender eller importerer.

Import af survey-data skal kunne identificere afvigelser mellem
eksisterende registrering og nye opmålingsdata.

Afvigelser skal præsenteres og behandles gennem systemets normale
ændrings- og godkendelsesarkitektur.

Survey-import må ikke lydløst overskrive gældende data, når der er en
reel afvigelse.

---

# 3. Upcoming

Upcoming betyder, at projektet er klar til produktionsplanlægning.

Planen kan fortsat udvikles og optimeres.

Ændringer behandles gennem den normale proces:

Forslag
→ Scenario
→ Konsekvensanalyse
→ Godkendelse
→ Gem

Upcoming betyder derfor ikke, at Rørbot eller andre klienter frit må
ændre gældende data uden godkendelse.

---

# 4. Active

Active betyder, at projektets udførelse er i gang.

Faktisk produktion registreres løbende.

Systemet skal kunne sammenholde:

- planlagt arbejde
- faktisk udført arbejde
- tidligere beslutninger
- ændringer
- afvigelser

Planen må fortsat ændres under udførelsen, men ændringer følger samme
scenario- og godkendelsesproces som øvrige ændringer.

Historikken må ikke overskrives.

---

# 5. Completed

Completed betyder, at projektet er afsluttet.

Projektets:

- tekniske data
- produktionsregistreringer
- snapshots
- beslutninger
- ændringer
- afvigelser

bevares som historik.

---

# 6. Produktion og løbende status

C5 Online leverer løbende produktionsregistreringer.

Produktionsoversigten beskriver den faktiske udførelse ude på
projektet.

Data kan blandt andet omfatte fremdrift for:

- opmåling
- forarbejde
- stikopmåling
- hovedledning
- stikåbning
- korthat
- langhat
- brøndarbejde
- DTVK

Brøndrapport/import kan levere yderligere oplysninger om arbejde på
brønde.

Produktionsdata beskriver faktisk udført arbejde.

De må ikke forveksles med planlagte aktiviteter.

---

# 7. Planmotorens grundprincip

Planmotoren modellerer virksomhedens faktiske produktionsproces.

Planen er en beregnet forventning.

Virkeligheden har altid forrang over planen.

Hvis faktisk registreret produktion afviger fra planen, skal systemet
registrere og forklare afvigelsen.

Planen må ikke omskrive virkeligheden for at få resultatet til at se
korrekt ud.

---

# 8. Hovedledning som styrende aktivitet

Hovedledningsarbejdet er en central styrende aktivitet i
produktionsplanlægningen.

Mange efterfølgende aktiviteter afhænger af hovedledningen.

Planmotoren skal samtidig kunne analysere virksomhedens samlede
kapacitet og må ikke optimere ét projekt isoleret, hvis det skaber en
dårligere samlet produktionsplan.

---

# 9. Normal aktivitetsrækkefølge

Den normale produktionsrækkefølge er:

Forarbejde
→ Hovedledning
→ Stikforberedelse
→ Stik
→ Kontrol
→ Korthat
→ Brønd
→ DTVK

Rækkefølgen beskriver virksomhedens normale workflow.

Den er ikke en påstand om, at virkeligheden aldrig kan afvige.

En afvigelse skal behandles som en eksplicit beslutning eller som
registreret faktisk udførelse.

Systemet må ikke skjule workflow-afvigelser.

---

# 10. Forarbejde

Forarbejde er en produktionsaktivitet.

Forarbejde er ikke survey.

Forarbejde kan blandt andet ændre eller bekræfte viden om stik og
andre faktiske forhold.

Når ny viden fremkommer gennem forarbejde eller produktion, skal den
registreres som faktisk projektinformation.

---

# 11. Afhængigheder og undtagelser

Afhængigheder beskriver den normale arbejdsgang.

Projektledelsen kan beslutte at fravige den normale rækkefølge.

En sådan fravigelse skal:

- være eksplicit
- have en begrundelse
- kunne analyseres
- kunne simuleres
- godkendes af et menneske
- registreres i beslutningshistorikken

Planner må anvende godkendte projektregler og undtagelser.

Rørbot må foreslå dem, men ikke selv godkende dem.

---

# 12. Plan og virkelighed er forskellige begreber

Systemet skal altid kunne skelne mellem:

- planlagt
- foreslået
- godkendt
- faktisk udført

Disse tilstande må ikke blandes sammen.

Et scenario er ikke en gældende plan.

En planlagt aktivitet er ikke udført arbejde.

En produktionsregistrering er ikke et forslag.

---

# 13. Datakilder

Gældende data gemmes i databasen.

Eksterne systemer som C5 er kilder til import og opdateringer.

CSV er et transportformat.

CSV er ikke Projektstyrings database.

Importer skal omsætte eksterne data til Projektstyrings generiske
domænemodel.

Efter import arbejder resten af systemet mod databasen og repositories,
ikke mod det specifikke C5-format.

---

# 14. Import og afvigelser

En import skal skelne mellem:

- nye oplysninger
- identiske oplysninger
- ændrede oplysninger
- manglende oplysninger
- ugyldige oplysninger

Nye og ændrede oplysninger skal behandles efter deres betydning.

Hvis en import ændrer allerede gældende tekniske data, skal ændringen
kunne vises som før/efter og følge den relevante
godkendelsesmekanisme.

Import må ikke skjule en ændring ved blot at overskrive den gamle
værdi.

---

# 15. Domænemodellen er autoritativ

Standardstruktur og feltdefinitioner skal have én autoritativ
implementering i den aktuelle database-/domænemodel.

Andre dele af systemet må ikke kopiere gamle dictionary- eller
JSON-strukturer som parallel model.

Når den autoritative model ændres, skal afhængige komponenter migreres.

Legacy-strukturer skal ikke holdes kunstigt i live.
