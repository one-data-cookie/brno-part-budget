# brno-part-budget

This repository provides data for the visualisation of projects submitted
to the [Brno's participatory budget](https://damenavas.cz/),
including public vote results.

To achieve this, the script does the following weekly:
- Downloads data on participatory budget projects through APIs
- Downloads public vote results from WordPress JSON endpoints
- Merges and cleans the data
- Pushes the resulting dataset into a Google Spreadsheet

To explore, visit the resulting [interactive dashboard on Tableau Public](https://public.tableau.com/views/ParticipativnrozpoetmstaBrna_17177050818370/NavigationDB).
Previously, it was also available on the Brno's data portal.

![Dashboard screenshot](./screenshot.png)

---

This project was initially developed as part of the Data Academy by [Czechitas](https://www.czechitas.cz/en/).

Collaborators:
- [Adéla Procházková](mailto:adelaprocha(at)gmail.com)
- [Elena Gorokhova](mailto:elena.o.gorokhova(at)gmail.com)
- [Michal Koláček](mailto:kolacek.m(at)gmail.com)
