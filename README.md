# Open Astronomy Catalog API

The Open Astronomy Catalog API (OACAPI) offers a lightweight, simple way to access data available via the Open Astronomy Catalogs (e.g. the Open Supernova, Tidal Disruption, and Kilonova Catalogs). The API is accessible via a route that works via any of the catalog domains,

https://astrocats.space/api/

https://sne.space/api/

https://tde.space/api/

https://kilonova.space/api/

where the only difference is preference in catalog when returning items that appear on multiple catalogs. For the examples below we will use the astrocats.space route. By default, all returned values are provided in JSON format, unless a `format=` URL variable is provided.

## Catalog queries

Whole catalog queries are used to find several objects that correspond to a given query, below we demonstrate a cone search about a set of coordinates:

https://astrocats.space/api/catalog/sne/?ra=12:12:12&dec:+33:33:33&

## Event queries

Individual event queries can return more-detailed information about each event, including datafiles such as spectra. Below, we show some examples of this in action:

#### Get the available redshift values for an event

https://astrocats.space/api/event/SN2014J/redshift

#### Select the first (preferred) value of the redshift

https://astrocats.space/api/event/SN2014J/redshift?item=0

#### Return all photometric observations with a magnitude, magnitude error, and band listed

https://astrocats.space/api/event/SN2014J/photometry/magnitude+e_magnitude+band

#### Return the above in CSV format

https://astrocats.space/api/event/SN2014J/photometry/magnitude+e_magnitude+band?format=csv

#### Return the spectrum closest to the listed MJD

https://astrocats.space/api/event/SN2014J/spectra?mjd=55500
