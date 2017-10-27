# Open Astronomy Catalog API

The Open Astronomy Catalog API (OACAPI) offers a lightweight, simple way to access data available via the Open Astronomy Catalogs (e.g. the Open Supernova, Tidal Disruption, and Kilonova Catalogs). The API is accessible via a route that works via any of the catalog domains,

https://astrocats.space/api/

https://sne.space/api/

https://tde.space/api/

https://kilonova.space/api/

where the only difference is preference in catalog when returning items that appear on multiple catalogs. For the examples below we will use the astrocats.space route. By default, all returned values are provided in JSON format, unless a `format=` URL variable is provided.

## Catalog queries

Whole catalog queries are used to find several objects that correspond to a given query. A few examples:

#### Cone search about a set of coordinates (not functional yet)

https://astrocats.space/api/catalog/sne/?ra=12:12:12&dec:+33:33:33&radius=2

#### Polygon search (*not implemented*)

#### Volume search (*not implemented*)

## Event queries

Individual event queries can return more-detailed information about each event, including datafiles such as spectra. Below, we show some examples of this in action:

#### Get the available redshift values for an event

https://astrocats.space/api/SN2014J/redshift

#### Select the first (preferred) value of the redshift (*not implemented*)

https://astrocats.space/api/SN2014J/redshift?item=0

#### Return all photometric observations with at least one of the `magnitude`, `e_magnitude`, and `band` attributes

https://astrocats.space/api/SN2014J/photometry/magnitude+e_magnitude+band

#### Return the above in CSV format

https://astrocats.space/api/SN2014J/photometry/magnitude+e_magnitude+band?format=csv

#### Only return observations that contain all requested attributes

https://astrocats.space/api/SN2014J/photometry/magnitude+e_magnitude+band?complete

#### Return observations for multiple events at once, in CSV format

https://astrocats.space/api/SN2014J+SN2015F/photometry/time+magnitude+band?format=csv

#### Return only observations matching given criteria, in this case band = B (*not implemented*)

https://astrocats.space/api/SN2014J/photometry/magnitude+e_magnitude+band?band=B

#### Return the spectrum closest to the listed MJD (*not implemented*)

https://astrocats.space/api/SN2014J/spectra?time~55500
