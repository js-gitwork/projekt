# Projektstyring – Planning Engine

## Formål

Planning Engine er ansvarlig for at omsætte projektdata til en gennemførlig produktionsplan.

Planning Engine foretager ingen vurderinger og ingen optimeringer.

Motorens eneste opgave er at producere den bedst mulige plan ud fra de regler og data, den modtager.

---

# Ansvarsområde

Planning Engine har ansvar for:

- beregning af aktiviteter
- aktiviteters rækkefølge
- varighed
- start- og slutdatoer
- afhængigheder mellem aktiviteter
- anvendelse af kalenderregler
- anvendelse af kapacitetsregler

Planning Engine har ikke ansvar for:

- økonomi
- geografi
- beslutningsstøtte
- anbefalinger
- AI
- simulering

Disse områder håndteres af Decision Engine.

---

# Input

Planning Engine modtager blandt andet:

- projekt
- installationer
- hold
- kalendere
- kapaciteter
- tildelinger
- planregler

Input skal være komplette og validerede.

---

# Output

Planning Engine returnerer en plan bestående af aktiviteter.

En aktivitet indeholder blandt andet:

- installation
- aktivitetstype
- hold
- startdato
- slutdato
- varighed

Output er udelukkende en beregnet plan.

---

# Grundlæggende planlægningsrækkefølge

Standardrækkefølgen er:

1. Forarbejde
2. Hovedledning
3. Stikforberedelse
4. Stik
5. Kontrol
6. Korthat
7. Brønd

Aktiviteter må ikke planlægges uden at deres forudsætninger er opfyldt.

---

# Installationen er den centrale enhed

Planning Engine planlægger på installationsniveau.

Hver installation behandles individuelt.

Projektplanen opstår som summen af installationernes aktiviteter.

---

# Hold

Alle aktiviteter udføres af et hold.

Hold vælges ud fra projektets tildelinger.

Planning Engine vurderer ikke om et andet hold ville være bedre.

Motoren anvender de tildelte hold.

---

# Kalender

Alle beregninger følger holdets kalender.

Kalenderen bestemmer:

- arbejdsdage
- ferie
- helligdage
- særlige arbejdsuger

Ingen aktivitet må planlægges uden for holdets kalender.

---

# Kapacitet

Aktiviteters varighed beregnes ud fra:

- antal enheder
- holdets kapacitet
- kalender

Eksempel:

30 stik

Kapacitet:

10 stik pr. dag

Varighed:

3 arbejdsdage

---

# Afhængigheder

Planning Engine respekterer alle afhængigheder.

Eksempel:

Stik kan ikke begynde før stikforberedelse.

Kontrol kan ikke begynde før stik.

Korthat kan ikke begynde før kontrol.

---

# Konflikter

Planning Engine forsøger ikke at løse konflikter.

Motoren registrerer dem.

Analyse og forslag håndteres af Decision Engine.

---

# Deterministisk beregning

Planning Engine skal altid levere samme resultat når input er identisk.

Der må ikke anvendes tilfældigheder.

Motoren skal være fuldt reproducerbar.

---

# Ingen forretningsmæssige vurderinger

Planning Engine svarer aldrig på spørgsmål som:

- Hvad er smartest?
- Hvad er billigst?
- Hvad bør vi gøre?

Motoren beregner kun planen.

---

# Samarbejde med Decision Engine

Planning Engine leverer grundlaget for analyser.

Decision Engine kan:

- ændre input
- simulere scenarier
- kalde Planning Engine igen
- sammenligne resultater

Planning Engine kender ikke Decision Engine.

---

# Fremtidige udvidelser

Planning Engine forventes senere udvidet med:

- maskinressourcer
- materiel
- flere aktivitetstyper
- flere kalenderregler
- flere kapacitetsmodeller

Udvidelser må ikke ændre motorens grundlæggende ansvar.

---

# Designprincip

Planning Engine producerer planer.

Decision Engine vurderer planerne.

Roerbot forklarer planerne.

Brugeren træffer beslutningen.
