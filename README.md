# Open Astronomy Catalog API v1.0

[![Website](https://img.shields.io/website-up-down-green-red/https/api.astrocats.space.svg?label=status)](https://github.com/astrocatalogs/OACAPI)
[![Calls](https://img.shields.io/badge/dynamic/json.svg?label=successful%20queries%20in%20last%20week&colorB=ff69b4&prefix=&suffix=&query=$.count&uri=https%3A%2F%2Fastrocats.space%2Fapi-count.php)](https://github.com/astrocatalogs/OACAPI)

The Open Astronomy Catalog API (OACAPI) offers a lightweight, simple way to access data available via the Open Astronomy Catalogs (e.g. the <a href="https://sne.space">Open Supernova</a>, <a href="https://tde.space">Tidal Disruption</a>, and <a href="https://kilonova.space">Kilonova</a> Catalogs). The API is accessible via a route that works via any of the catalog domains,

https://api.astrocats.space/

https://api.sne.space/

https://api.tde.space/

https://api.kilonova.space/

where the only difference is preference in catalog when returning items that appear on multiple catalogs. For the examples below we will use the api.astrocats.space route. By default, all returned values are provided in JSON format, unless a `format=` URL variable is provided.

## General use

The pattern for the API is one of the domains listed above (e.g. `https://api.astrocats.space`) followed by

`/EVENT/QUANTITY/ATTRIBUTE?ARGUMENT1=VALUE1&ARGUMENT2=VALUE2&...`

where `EVENT` is set to a transient's name, `QUANTITY` is set to a desired quantity to retrieve (e.g. redshift), `ATTRIBUTE` is a property of that quantity, and the `ARGUMENT` variables allow to user to filter data based upon various attribute values. The `ARGUMENT` variables can either be used to guarantee that a certain attribute appears in the returned results (e.g. adding `&time&e_magnitude` to the query will guarantee that each returned item has a `time` and `e_magnitude` attribute), or used to filter via a simple equality such as `telescope=HST` (which would only return `QUANTITY` objects where the `telescope` attribute equals `"HST"`), or they can be more powerful for certain filter attributes (examples being `ra` and `dec` for performing cone searches).

Key names that are usable in API calls can be found in the [OAC schema](https://github.com/astrocatalogs/schema). Below, we provide some example queries that demonstrate the API's capabilities.

### Special arguments

There are a few arguments that have special meaning and are only a part of the API, not the schema:

* `closest`: Return the quantities with the closest value to the specified attributes. If multiple attributes are specified, the closest to each will be returned (e.g., `magnitude=15&time=56789&closest` would return *both* the observation with magnitude closest to 15 and time closest to 56789.
* `complete`: Return only quantities containing all of the requested attributes.
* `first`: Return only the first of each of the listed quantities.
* `format=x`: Return data in the specified format `x`, currently supports `csv` and `tsv`. Any other format specification will return `JSON`.
* `item=n`: Return only the `n`th item of each of the listed quantities.
* `radius=r`: Return events within a distance `r` (in arcseconds) of a given set of `ra` and `dec` coordinates. Note that this disables exact matches for `ra` and `dec`.
* `width=w`: Return events within a distance `w` (in arcseconds) of a given `ra` value (for box searches).
* `height=h`: Return events within a distance `h` (in arcseconds) of a given `dec` value (for box searches).
* `sortby=s`: Sort the returned array by the attribute `s` (only works when returning results in `csv`/`tsv` formats).

## Example queries

#### Return all events within a 2" cone about a set of coordinates

https://api.astrocats.space?ra=21:23:32.16&dec=-53:01:36.08&radius=2

#### Return all supernova metadata in CSV format

https://api.sne.space/catalog?format=CSV

By default, queries such as the two above will return the catalog entries for events that satisfy the search conditions. To return data from a specific catalog when searching by a criterion such as position, the user should insert `catalog/` into the URL before the rest of the query of the specific catalog they are interested in, as shown in the example below:

#### Redshifts of all supernovae with a redshift reported within 5° of a coordinate, in CSV format

https://api.sne.space/catalog/redshift?ra=10:42:16.88&dec=-24:13:12.13&radius=18000&format=csv&redshift

If the user instead wishes to return info on all events across all catalogs, the `all/` route should be used instead (any URL can be used with this route):

#### Redshifts of all events with a redshift reported within 5° of a coordinate, in CSV format

https://api.astrocats.space/all/redshift?ra=10:42:16.88&dec=-24:13:12.13&radius=18000&format=csv&redshift

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

#### Sort the returned photometry by magnitude

https://api.astrocats.space/SN2014J/photometry/magnitude+e_magnitude+band?format=csv&sortby=magnitude

#### Return observations for multiple events at once, in CSV format

https://api.astrocats.space/SN2014J+SN2015F/photometry/time+magnitude+band?format=csv

#### Return only observations whose attributes include the listed keys (`e_magnitude` and `band`)

https://api.astrocats.space/SN2014J/photometry/time+magnitude+e_magnitude+band?e_magnitude&band

#### Return only observations matching given criteria, in this case band = B

https://api.astrocats.space/SN2014J/photometry/magnitude+e_magnitude+band?band=B

In the following example, we filter upon the `value` of `claimedtype`, but note that this filters `lumdist` as well, since the `value` filter applies to both:

#### Luminosity distances and claimed types of all events with luminosity distance *and* claimed type equal to Ia (probably not what you intend!)

https://api.astrocats.space/all/lumdist+claimedtype?value=ia

Note that the above returns an empty result. Instead, we want to do:

#### Luminosity distances and claimed types of all events with an available luminosity distance and "Ia" listed as a type, in TSV format

https://api.astrocats.space/all/lumdist+claimedtype?lumdist&claimedtype=ia&format=tsv

#### Return the spectrum closest to the listed MJD

https://api.astrocats.space/SN2014J/spectra/time+data?time=56703.2&closest

The `all/` route (combined with filtering) can also return data from the individual event files if data isn't contained within the main OAC catalog files (i.e. the data that is visible on the main pages of the Open Supernova Catalog, etc.). Because these queries are expensive (the full dataset must be loaded for each event), they have some numeric limits to prevent overloading the server.

#### Return all photometry in a 2" radius about a coordinate, in CSV format

https://api.astrocats.space/all/photometry/time+band+magnitude?ra=21:23:32.16&dec=-53:01:36.08&radius=2&format=csv

#### Return the instruments used to produce spectra within a 5° of a given coordinate, in CSV format

https://api.astrocats.space/all/spectra/instrument?ra=21:23:32.16&dec=-53:01:36.08&radius=18000&format=csv
