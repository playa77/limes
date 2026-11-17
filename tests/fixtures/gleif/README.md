# GLEIF acceptance fixture (BE-59)

`lei_records.json` is a constructed LEI API page (the shape of
`api.gleif.org/api/v1/lei-records`) with the four synthetic `5493000TEST…`
entities the acceptance graph has always used, relocated to NRW addresses:
an active Köln company with a direct LEI parent, an active foreign parent, an
active entity without a headquarters address, and a lapsed Düsseldorf entity
that must not load. Real captured pages live in `../gleif_api/`.
