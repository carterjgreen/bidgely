# Bidgely

A Python library for getting historical and forecasted usage/cost from utilities that use Bidgely such as Hydro Ottawa.

Supported utilities:

- Hydro Ottawa

Possible Supports:

- BC Hydro
- NS Power
- Hydro One
- Public Service Electric and Gas (PSE&G)

More [here](https://www.bidgely.com/customers/)

## Support a new utility

To add support for a new utility that uses the Bidgely NA API (you can tell if the energy dashboard of your utility makes network requests to naapi-read.bidgely.com in the network tab of your browser's developer tools) add a file similar to
[hydroottawa.py](https://github.com/carterjgreen/bidgely/blob/main/src/opower/utilities/pge.py)

Name the file after the utility , e.g. hydroottawa.py for Hydro Ottawa or bchydro.py for BC Hydro.

Since this library is planned to be used by Home Assistant, then per <https://github.com/home-assistant/architecture/blob/master/adr/0004-webscraping.md> we cannot have a dependency on a headless browser and we can only parse HTML during login.

> An exception is made for the authentication phase. An integration is allowed to extract fields from forms. To make it more robust, data should not be gathered by scraping individual fields but instead scrape all fields at once.

## Example

See [demo.py](https://github.com/carterjgreen/bidgely/blob/main/examples/demo.py)

## Thank you

Inspired by opower by [@tronikos](https://www.github.com/tronikos)

Async pycognito sign in from [@dotKrad](https://www.github.com/dotKrad)
