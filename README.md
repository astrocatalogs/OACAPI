# Open Astronomy Catalog API v1.0

The Open Astronomy Catalog API (OACAPI) offers a lightweight, simple way to access data available via the Open Astronomy Catalogs (e.g. the Open Supernova, Tidal Disruption, and Kilonova Catalogs). The API is accessible via a route that works via any of the catalog domains,

https://api.astrocats.space/

https://api.sne.space/

https://api.tde.space/

https://api.kilonova.space/

where the only difference is preference in catalog when returning items that appear on multiple catalogs. For the examples below we will use the api.astrocats.space route. By default, all returned values are provided in JSON format, unless a `format=` URL variable is provided.

## General use

The pattern for the API is one of the domains listed above (e.g. `https://api.astrocats.space`) followed by

`/EVENT/QUANTITY/ATTRIBUTE?ARGUMENT1=VALUE1&ARGUMENT2=VALUE2&...`

where `EVENT` is set to a transient's name, `QUANTITY` is set to a desired quantity to retrieve (e.g. redshift), `ATTRIBUTE` is a property of that quantity, and the `ARGUMENT` variables allow to user to filter data based upon various attribute values. The `ARGUMENT` variables can either filter via a simple equality such as `telescope=HST`, which would only return `QUANTITY` objects where the `telescope` attribute equals `"HST"`, or they can be more powerful for certain filter attributes (examples being `ra` and `dec` for doing cone searches).

Key names that are usable in API calls can be found in the [OAC schema](https://github.com/astrocatalogs/schema). Below, we provide some example queries that demonstrate the API's capabilites.

### Special arguments

There are a few arguments that have special meaning and are only a part of the API, not the schema:

* `closest`: Return the quantities with the closest value to the specified attributes. If multiple attributes are specified, the closest to each will be return (e.g., `magnitude=15&time=56789&closest` would return *both* the observation with magnitude closest to 15 and time closest to 56789.
* `complete`: Return only quantities containing all of the requested attributes.
* `first`: Return only the first of each of the listed quantities.
* `format=x`: Return data in the specified format `x`, currently supports `csv` and `tsv`. Any other format specification will return `JSON`.
* `item=n`: Return only the first `n` of each of the listed quantities.
* `radius=r`: Return events within a distance `r` (in arcseconds) of a given set of `ra` and `dec` coordinates. Note that this disables exact matches for `ra` and `dec`.

## Example queries

#### Return all events within a 2" cone about a set of coordinates

https://api.astrocats.space?ra=21:23:32.16&dec=-53:01:36.08&radius=2

By default, queries such as the one above will return the catalog JSON entries for events that satisfy the search conditions. To return data from the catalog when searching by a criterion such as position, the user should insert `all/` into the URL before the rest of the query, as shown in the example below:

#### Redshifts of all supernovae within 5° of a coordinate

https://api.astrocats.space/all/redshift/value?ra=10:42:16.88&dec=-24:13:12.13&radius=18000&format=csv

Individual event queries can return more-detailed information about each event, including datafiles such as spectra. Below, we show some examples of this in action:

#### Get the available redshift values for an event

https://api.astrocats.space/SN2014J/redshift

#### Select the first (preferred) value of the redshift

https://api.astrocats.space/SN2014J/redshift?first, or
https://api.astrocats.space/SN2014J/redshift?item=0

#### Return all photometric observations with at least one of the `magnitude`, `e_magnitude`, and `band` attributes

https://api.astrocats.space/SN2014J/photometry/magnitude+e_magnitude+band

#### Return the above in CSV format

https://api.astrocats.space/SN2014J/photometry/magnitude+e_magnitude+band?format=csv

#### Only return observations that contain all requested attributes

https://api.astrocats.space/SN2014J/photometry/magnitude+e_magnitude+band?complete

#### Return observations for multiple events at once, in CSV format

https://api.astrocats.space/SN2014J+SN2015F/photometry/time+magnitude+band?format=csv

#### Return only observations matching given criteria, in this case band = B

https://api.astrocats.space/SN2014J/photometry/magnitude+e_magnitude+band?band=B

#### Return the spectrum closest to the listed MJD

https://api.astrocats.space/SN2014J/spectra/time?time=56703.2&closest

The `all/` route (combined with filtering) can also return data from the individual event files if data isn't contained within the main OAC catalog files (i.e. the data that is visible on the main pages of the Open Supernova Catalog, etc.). Because these queries are expensive (the full dataset must be loaded for each event), they have some numeric limits to prevent overloading the server.

#### Return all photometry in a 2" radius about a coordinate

https://api.astrocats.space/all/photometry/time+band+magnitude?ra=21:23:32.16&dec=-53:01:36.08&radius=2&format=csv

#### Return the instruments used to produce spectra within a 5° of a given coordinate

https://api.astrocats.space/all/spectra/instrument?ra=21:23:32.16&dec=-53:01:36.08&radius=18000&format=csv
